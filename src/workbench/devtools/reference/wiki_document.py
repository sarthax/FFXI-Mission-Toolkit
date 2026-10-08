"""Structured wiki document storage, rendering blocks, and multilingual search helpers."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from html.parser import HTMLParser

import mwparserfromhell

PARSER_VERSION = "wiki-doc-v3-table-fields"


def normalize_search(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold().replace("　", " ")
    return " ".join(value.split())


def init_db(con: sqlite3.Connection) -> None:
    con.executescript("""
    CREATE TABLE IF NOT EXISTS reference_wiki_documents(
      source_id TEXT NOT NULL,page_id TEXT NOT NULL,source_format TEXT NOT NULL,
      raw_source TEXT,raw_hash TEXT,parser_version TEXT NOT NULL,
      parsed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(source_id,page_id));
    CREATE TABLE IF NOT EXISTS reference_wiki_blocks(
      source_id TEXT NOT NULL,page_id TEXT NOT NULL,block_id TEXT NOT NULL,ordinal INTEGER NOT NULL,
      block_type TEXT NOT NULL,heading_level INTEGER,section_path TEXT,text TEXT,target TEXT,
      metadata_json TEXT NOT NULL DEFAULT '{}',source_locator TEXT,
      PRIMARY KEY(source_id,page_id,block_id));
    CREATE INDEX IF NOT EXISTS idx_reference_wiki_blocks_page
      ON reference_wiki_blocks(source_id,page_id,ordinal);
    CREATE TABLE IF NOT EXISTS reference_wiki_aliases(
      alias_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,page_id TEXT NOT NULL,alias TEXT NOT NULL,
      norm_alias TEXT NOT NULL,language TEXT,alias_type TEXT NOT NULL,provenance TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE INDEX IF NOT EXISTS idx_reference_wiki_alias_norm ON reference_wiki_aliases(norm_alias);
    CREATE INDEX IF NOT EXISTS idx_reference_wiki_alias_page ON reference_wiki_aliases(source_id,page_id);
    CREATE TABLE IF NOT EXISTS reference_wiki_topics(
      topic_id TEXT PRIMARY KEY,canonical_title TEXT NOT NULL,norm_title TEXT NOT NULL UNIQUE,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS reference_wiki_topic_pages(
      topic_id TEXT NOT NULL,source_id TEXT NOT NULL,page_id TEXT NOT NULL,
      link_method TEXT NOT NULL DEFAULT 'MANUAL',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(topic_id,source_id,page_id));
    CREATE INDEX IF NOT EXISTS idx_reference_wiki_topic_page
      ON reference_wiki_topic_pages(source_id,page_id);
    """)
    con.execute("""CREATE TABLE IF NOT EXISTS reference_wiki_topic_dismissals(
      source_id TEXT NOT NULL,page_id TEXT NOT NULL,topic_id TEXT NOT NULL,
      dismissed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(source_id,page_id,topic_id))""")
    con.commit()


def dismiss_topic_suggestion(con, *, source_id: str, page_id: str, topic_id: str) -> None:
    """Hide a suggested topic for one page; never unlink existing topics."""
    init_db(con)
    if page_topic(con,source_id,page_id):
        raise ValueError("Page already has a topic link")
    if not any(x["topic_id"]==topic_id for x in suggest_topic_links(con,source_id=source_id,page_id=page_id)):
        raise ValueError("Topic is not a current suggestion")
    con.execute("""INSERT OR IGNORE INTO reference_wiki_topic_dismissals
      (source_id,page_id,topic_id) VALUES (?,?,?)""",(source_id,str(page_id),topic_id))
    con.commit()


def _block(page_id: str, ordinal: int, block_type: str, text: str = "", **kw) -> dict:
    raw = f"{page_id}|{ordinal}|{block_type}|{text[:120]}"
    return {
        "block_id": "wb:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20],
        "ordinal": ordinal,
        "block_type": block_type,
        "heading_level": kw.get("heading_level"),
        "section_path": kw.get("section_path"),
        "text": (text or "").strip(),
        "target": kw.get("target"),
        "metadata": kw.get("metadata") or {},
        "source_locator": kw.get("source_locator"),
    }


def mediawiki_blocks(page_id: str, wikitext: str) -> list[dict]:
    code = mwparserfromhell.parse(wikitext or "")
    blocks, stack, paragraph = [], [], []
    ordinal, in_table = 0, False

    def path():
        return " > ".join(x[1] for x in stack) or None

    def emit(kind, text="", **kw):
        nonlocal ordinal
        text = (text or "").strip()
        if not text and kind not in {"table_start", "table_end", "table_row"}:
            return
        ordinal += 1
        blocks.append(_block(page_id, ordinal, kind, text, section_path=path(), **kw))

    def flush():
        nonlocal paragraph
        if paragraph:
            raw = " ".join(x.strip() for x in paragraph if x.strip())
            clean = str(mwparserfromhell.parse(raw).strip_code(normalize=True, collapse=True)).strip()
            emit("paragraph", re.sub(r"\s+", " ", clean))
            paragraph = []

    for line in str(code).splitlines():
        m = re.match(r"^\s*(={2,6})\s*(.+?)\s*\1\s*$", line)
        if m:
            flush()
            level = len(m.group(1))
            title = str(mwparserfromhell.parse(m.group(2)).strip_code()).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            emit("heading", title, heading_level=level, source_locator=f"section:{title}")
            continue
        if line.startswith("{|"):
            flush(); in_table = True; emit("table_start", "table"); continue
        if in_table and line.startswith("|}"):
            emit("table_end", "table"); in_table = False; continue
        if in_table and line.startswith("|-"):
            emit("table_row", "row"); continue
        if in_table and line.startswith(("!", "|")):
            kind = "table_header_cell" if line.startswith("!") else "table_cell"
            for cell in re.split(r"!!|\|\|", line[1:]):
                raw_cell=cell.strip()
                clean = str(mwparserfromhell.parse(raw_cell).strip_code(normalize=True, collapse=True)).strip()
                emit(kind, clean, metadata={"raw_value":raw_cell, "review_only":True},
                     source_locator=f"block:{page_id}:table-cell:{ordinal + 1}")
            continue
        lm = re.match(r"^\s*([*#;:]+)\s*(.*)$", line)
        if lm:
            flush()
            marker, body = lm.groups()
            clean = str(mwparserfromhell.parse(body).strip_code(normalize=True, collapse=True)).strip()
            kind = "definition_term" if marker.startswith(";") else "definition" if marker.startswith(":") else "list_item"
            emit(kind, clean, metadata={"marker": marker, "depth": len(marker)})
            continue
        if not line.strip():
            flush()
        else:
            paragraph.append(line)
    flush()

    # Preserve links with the section in which they actually occur.  Typed relationship
    # extraction relies on this source location, so do not inherit the parser's final section.
    seen = set()
    for section in code.get_sections(include_headings=True, flat=True):
        headings=section.filter_headings()
        section_title=str(headings[0].title).strip() if headings else ""
        for link in section.filter_wikilinks(recursive=True):
            target = str(link.title).split("#", 1)[0].strip()
            label = str(link.text or link.title).strip()
            key=(section_title.casefold(),target.casefold(),label)
            if not target or key in seen:
                continue
            seen.add(key)
            ordinal += 1
            blocks.append(_block(
                page_id,ordinal,"link",label,target=target,
                section_path=section_title or None,
                metadata={"hidden":True},
                source_locator=(f"section:{section_title}:wikilink:{target}" if section_title else f"wikilink:{target}"),
            ))
    # Named template parameters are preserved as inspectable fields, not
    # inferred gameplay relationships. MediaWiki templates can contain nested
    # expressions; only explicit names are surfaced, with original wikitext
    # retained on the document for deeper/manual interpretation.
    for section in code.get_sections(include_headings=True, flat=True):
        headings=section.filter_headings()
        section_title=str(headings[0].title).strip() if headings else ""
        for template_index, template in enumerate(section.filter_templates(recursive=False), 1):
            template_name=str(template.name).strip()
            if not template_name:
                continue
            for param_index,param in enumerate(template.params,1):
                if not param.showkey:
                    continue  # positional parameters have no reliable field label
                field_name=str(param.name).strip()
                if not field_name:
                    continue
                raw_value=str(param.value).strip()
                display=str(mwparserfromhell.parse(raw_value).strip_code(normalize=True,collapse=True)).strip()
                ordinal+=1
                blocks.append(_block(
                    page_id,ordinal,"template_field",display,
                    section_path=section_title or None,
                    metadata={"template":template_name,"field":field_name,
                              "raw_value":raw_value,"review_only":True},
                    source_locator=f"section:{section_title}:template:{template_index}:field:{param_index}",
                ))
    return blocks


class _HTMLBlocks(HTMLParser):
    def __init__(self, page_id: str):
        super().__init__(convert_charrefs=True)
        self.page_id, self.blocks, self.ordinal = page_id, [], 0
        self.stack, self.sections = [], []

    def path(self):
        return " > ".join(x[1] for x in self.sections) or None

    def emit(self, kind, text="", **kw):
        text = re.sub(r"\s+", " ", text or "").strip()
        if not text and kind not in {"table_start", "table_end", "table_row"}:
            return
        self.ordinal += 1
        self.blocks.append(_block(self.page_id, self.ordinal, kind, text, section_path=self.path(), **kw))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style", "noscript"}:
            self.stack.append((tag, {"ignore": True, "text": []})); return
        if tag in {"h1","h2","h3","h4","h5","h6","p","li","dt","dd","th","td","a"}:
            self.stack.append((tag, {"attrs": attrs, "text": []}))
        elif tag == "table":
            self.emit("table_start", "table")
        elif tag == "tr":
            self.emit("table_row", "row")
        elif tag == "br" and self.stack:
            self.stack[-1][1]["text"].append("\n")

    def handle_data(self, data):
        if self.stack and not self.stack[-1][1].get("ignore"):
            self.stack[-1][1]["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "table":
            self.emit("table_end", "table"); return
        for i in range(len(self.stack)-1, -1, -1):
            open_tag, state = self.stack[i]
            if open_tag != tag:
                continue
            self.stack.pop(i)
            if state.get("ignore"):
                return
            text = "".join(state["text"])
            if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
                level, title = int(tag[1]), re.sub(r"\s+", " ", text).strip()
                while self.sections and self.sections[-1][0] >= level:
                    self.sections.pop()
                self.sections.append((level, title))
                self.emit("heading", title, heading_level=level, source_locator=f"section:{title}")
            elif tag == "p": self.emit("paragraph", text)
            elif tag == "li": self.emit("list_item", text, metadata={"depth": 1})
            elif tag == "dt": self.emit("definition_term", text)
            elif tag == "dd": self.emit("definition", text)
            elif tag == "th": self.emit("table_header_cell", text)
            elif tag == "td": self.emit("table_cell", text)
            elif tag == "a":
                href = state["attrs"].get("href")
                if href: self.emit("link", text or href, target=href, metadata={"hidden": True})
            if self.stack and text:
                self.stack[-1][1]["text"].append(text)
            return


def html_blocks(page_id: str, raw_html: str) -> list[dict]:
    # WikiWiki pages include navigation/tool chrome around the article. Keep the full raw source
    # in reference_wiki_documents, but structure only the article body so nav/footer links do not
    # become reference claims.
    source=raw_html or ""
    m=re.search(r'<div[^>]+id=["\']body["\'][^>]*>(.*?)(?=<div[^>]+id=["\'](?:footer|toolbar|bottom)["\'])',source,re.S|re.I)
    if m:
        source=m.group(1)
    parser = _HTMLBlocks(page_id); parser.feed(source); return parser.blocks


def legacy_text_blocks(page_id: str, text: str) -> list[dict]:
    chunks = [x.strip() for x in re.split(r"\n\s*\n+", text or "") if x.strip()]
    if not chunks and (text or "").strip():
        chunks = [(text or "").strip()]
    return [_block(page_id, i+1, "legacy_text", chunk, metadata={"degraded": True}) for i, chunk in enumerate(chunks)]


def build_blocks(page: dict, *, source_format: str | None = None, raw_source: str | None = None):
    page_id = str(page.get("pageid") or page.get("page_id") or page.get("title") or "")
    if raw_source is None and "wikitext" in page:
        source_format, raw_source = source_format or "mediawiki", page.get("wikitext") or ""
    elif raw_source is None:
        source_format, raw_source = source_format or "legacy_text", page.get("page_text") or ""
    if source_format == "html": blocks = html_blocks(page_id, raw_source or "")
    elif source_format == "mediawiki": blocks = mediawiki_blocks(page_id, raw_source or "")
    else: blocks = legacy_text_blocks(page_id, raw_source or "")
    return page_id, source_format or "legacy_text", blocks


def store_document(con, *, source_id, page_id, source_format, raw_source, blocks):
    init_db(con)
    raw_hash = hashlib.sha256((raw_source or "").encode("utf-8")).hexdigest()
    # A repeat scrape of identical source under the same parser must not churn
    # block identities, parsed_at, or review-facing evidence projections. Rebuild
    # when a parser upgrade changes interpretation, or when blocks are absent.
    previous = con.execute("""SELECT raw_hash, parser_version FROM reference_wiki_documents
      WHERE source_id=? AND page_id=?""", (source_id, page_id)).fetchone()
    if previous == (raw_hash, PARSER_VERSION) and con.execute(
        "SELECT 1 FROM reference_wiki_blocks WHERE source_id=? AND page_id=? LIMIT 1",
        (source_id, page_id),
    ).fetchone():
        return
    con.execute("""INSERT OR REPLACE INTO reference_wiki_documents
      (source_id,page_id,source_format,raw_source,raw_hash,parser_version,parsed_at)
      VALUES (?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
      (source_id,page_id,source_format,raw_source,raw_hash,PARSER_VERSION))
    con.execute("DELETE FROM reference_wiki_blocks WHERE source_id=? AND page_id=?", (source_id,page_id))
    con.executemany("""INSERT INTO reference_wiki_blocks
      (source_id,page_id,block_id,ordinal,block_type,heading_level,section_path,text,target,metadata_json,source_locator)
      VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
      [(source_id,page_id,b["block_id"],b["ordinal"],b["block_type"],b.get("heading_level"),b.get("section_path"),
        b.get("text"),b.get("target"),json.dumps(b.get("metadata") or {},ensure_ascii=False,sort_keys=True),b.get("source_locator"))
       for b in blocks])
    con.commit()


def stored_blocks(con, source_id: str, page_id: str) -> list[dict]:
    init_db(con)
    rows = con.execute("""SELECT block_id,ordinal,block_type,heading_level,section_path,text,target,metadata_json,source_locator
      FROM reference_wiki_blocks WHERE source_id=? AND page_id=? ORDER BY ordinal""",(source_id,page_id)).fetchall()
    return [{"block_id":r[0],"ordinal":r[1],"block_type":r[2],"heading_level":r[3],"section_path":r[4],
             "text":r[5] or "","target":r[6],"metadata":json.loads(r[7] or "{}"),"source_locator":r[8]} for r in rows]



def presentation_groups(blocks: list[dict]) -> list[dict]:
    """Group the structural stream into renderer-friendly sections/lists/tables."""
    sections=[{"title":"Overview","level":1,"content":[]}]
    current=sections[0]
    i=0
    while i < len(blocks):
        b=blocks[i]
        kind=b.get("block_type")
        if kind=="heading":
            current={"title":b.get("text") or "Section","level":b.get("heading_level") or 2,"content":[]}
            sections.append(current); i+=1; continue
        if kind=="list_item":
            items=[]
            while i < len(blocks) and blocks[i].get("block_type")=="list_item":
                items.append({
                    "text":blocks[i].get("text") or "",
                    "depth":max(1,int((blocks[i].get("metadata") or {}).get("depth") or 1)),
                    "marker":(blocks[i].get("metadata") or {}).get("marker") or "*",
                }); i+=1
            current["content"].append({"type":"list","items":items}); continue
        if kind=="template_field":
            metadata=b.get("metadata") or {}
            current["content"].append({"type":"definition","term":str(metadata.get("template") or "Template")+": "+str(metadata.get("field") or "Field"),"definition":b.get("text") or ""})
            i+=1; continue
        if kind=="definition_term":
            term=b.get("text") or ""; definition=""
            if i+1 < len(blocks) and blocks[i+1].get("block_type")=="definition":
                definition=blocks[i+1].get("text") or ""; i+=1
            current["content"].append({"type":"definition","term":term,"definition":definition}); i+=1; continue
        if kind=="table_start":
            rows=[]; row=[]; headers=False; i+=1
            while i < len(blocks) and blocks[i].get("block_type")!="table_end":
                tb=blocks[i]; tk=tb.get("block_type")
                if tk=="table_row":
                    if row: rows.append(row); row=[]
                elif tk in {"table_cell","table_header_cell"}:
                    headers=headers or tk=="table_header_cell"
                    row.append({"text":tb.get("text") or "","header":tk=="table_header_cell",
                                "source_locator":tb.get("source_locator"),
                                "raw_value":(tb.get("metadata") or {}).get("raw_value")})
                i+=1
            if row: rows.append(row)
            # A heading and an explicit first-column label make a useful
            # *review candidate*, not proof of a gameplay relationship.
            # Keep these annotations purely in presentation, never in graph imports.
            labels={"drops","drop","loot","rewards","reward","requirements","prerequisites","location","zone",
                    "戦利品","ドロップ","報酬","必要条件","参加条件","場所","エリア"}
            candidates=[]
            for row_index, cells in enumerate(rows):
                if len(cells)<2:
                    continue
                label=normalize_search(cells[0]["text"])
                if label not in labels:
                    continue
                value=cells[1]["text"].strip()
                if value:
                    candidates.append({"row_index":row_index,"field":cells[0]["text"],
                                       "value":value,"review_only":True,
                                       "value_source_locator":cells[1].get("source_locator"),
                                       "value_raw":cells[1].get("raw_value"),
                                       "field_source_locator":cells[0].get("source_locator")})
            current["content"].append({"type":"table","rows":rows,"has_headers":headers,
                                       "field_candidates":candidates})
            i+=1; continue
        if kind in {"paragraph","legacy_text","definition"}:
            current["content"].append({
                "type":"legacy_text" if kind=="legacy_text" else "paragraph",
                "text":b.get("text") or "",
                "degraded":bool((b.get("metadata") or {}).get("degraded")),
            })
        i+=1
    return [section for section in sections if section["content"] or section["title"]!="Overview"]



def add_alias(con, *, source_id, page_id, alias, language=None, alias_type="MANUAL", provenance="manual"):
    alias=(alias or "").strip()
    if not alias: return
    init_db(con); norm=normalize_search(alias)
    aid="wiki-alias:"+hashlib.sha1("|".join((source_id,str(page_id),norm,alias_type,provenance)).encode()).hexdigest()[:24]
    con.execute("""INSERT OR REPLACE INTO reference_wiki_aliases
      (alias_id,source_id,page_id,alias,norm_alias,language,alias_type,provenance)
      VALUES (?,?,?,?,?,?,?,?)""",(aid,source_id,str(page_id),alias,norm,language,alias_type,provenance))


def ensure_title_alias(con, source_id: str, page_id: str, title: str):
    add_alias(con,source_id=source_id,page_id=page_id,alias=title,
              language="ja" if source_id=="WikiWikiJP" else "en",alias_type="SOURCE_TITLE",provenance=source_id)
    con.commit()


def link_topic(con, *, source_id: str, page_id: str, canonical_title: str, method: str = "MANUAL") -> dict:
    """Attach a source page to a language-neutral topic keyed by its canonical English label."""
    canonical_title=(canonical_title or "").strip()
    if not canonical_title:
        raise ValueError("canonical_title is required")
    init_db(con)
    norm=normalize_search(canonical_title)
    topic_id="wiki-topic:"+hashlib.sha1(norm.encode("utf-8")).hexdigest()[:20]
    con.execute("""INSERT OR IGNORE INTO reference_wiki_topics(topic_id,canonical_title,norm_title)
      VALUES (?,?,?)""",(topic_id,canonical_title,norm))
    con.execute("""INSERT OR REPLACE INTO reference_wiki_topic_pages
      (topic_id,source_id,page_id,link_method) VALUES (?,?,?,?)""",
      (topic_id,source_id,str(page_id),method))
    add_alias(con,source_id=source_id,page_id=str(page_id),alias=canonical_title,
              language="en",alias_type="CANONICAL_TOPIC",provenance=method)
    con.commit()
    return {"topic_id":topic_id,"canonical_title":canonical_title}



def suggest_topic_links(con, *, source_id: str, page_id: str, limit: int = 20) -> list[dict]:
    """Suggest existing reviewed topics by exact title/alias match; never write links.

    This is a deterministic review queue, not a translation system. In
    particular, generated translations are not considered topic evidence.
    """
    init_db(con)
    page=con.execute(
        "SELECT title FROM reference_wiki_pages WHERE source_id=? AND page_id=?",
        (source_id,str(page_id)),
    ).fetchone()
    if not page or page_topic(con,source_id,str(page_id)):
        return []
    norm=normalize_search(page[0])
    if not norm:
        return []
    # Only user/reviewer-established aliases count. Exclude machine-produced
    # text and aliases attached to the source page itself.
    rows=con.execute("""
      SELECT DISTINCT t.topic_id,t.canonical_title,a.source_id,a.page_id
      FROM reference_wiki_aliases a
      JOIN reference_wiki_topic_pages p
        ON p.source_id=a.source_id AND p.page_id=a.page_id
      JOIN reference_wiki_topics t ON t.topic_id=p.topic_id
      WHERE a.norm_alias=? AND a.alias_type IN ('MANUAL','CANONICAL_TOPIC')
        AND a.provenance NOT LIKE '%MACHINE%'
        AND NOT (a.source_id=? AND a.page_id=?)
      ORDER BY t.canonical_title,t.topic_id
    """,(norm,source_id,str(page_id))).fetchall()
    topics={}
    for topic_id,title,matched_source,matched_page in rows:
        if con.execute("SELECT 1 FROM reference_wiki_topic_dismissals WHERE source_id=? AND page_id=? AND topic_id=?",
                       (source_id,str(page_id),topic_id)).fetchone():
            continue
        item=topics.setdefault(topic_id,{"topic_id":topic_id,"canonical_title":title,
            "match_method":"EXACT_REVIEWED_ALIAS","review_only":True,"supporting_pages":[]})
        item["supporting_pages"].append({"source_id":matched_source,"page_id":str(matched_page)})
    return list(topics.values())[:max(0,min(limit,100))]


def topic_review_queue(con, *, source_id: str, limit: int = 50) -> list[dict]:
    """Read-only bounded queue of pages with pending or dismissed topic suggestions.

    Dismissed entries remain visible for audit but never reappear as pending.
    """
    init_db(con)
    pages=con.execute("""
      SELECT w.page_id,w.title
      FROM reference_wiki_pages w
      WHERE w.source_id=?
        AND NOT EXISTS (
          SELECT 1 FROM reference_wiki_topic_pages p
          WHERE p.source_id=w.source_id AND p.page_id=w.page_id
        )
      ORDER BY w.title,w.page_id LIMIT ?
    """,(source_id,max(0,min(limit,200)))).fetchall()
    queue=[]
    for page_id,title in pages:
        pending=suggest_topic_links(con,source_id=source_id,page_id=str(page_id))
        dismissed=[{"topic_id":t,"canonical_title":label}
          for t,label in con.execute("""
            SELECT d.topic_id,COALESCE(t.canonical_title,'[missing topic]')
            FROM reference_wiki_topic_dismissals d
            LEFT JOIN reference_wiki_topics t ON t.topic_id=d.topic_id
            WHERE d.source_id=? AND d.page_id=?
            ORDER BY label,d.topic_id
          """,(source_id,str(page_id))).fetchall()]
        if pending or dismissed:
            queue.append({"source_id":source_id,"page_id":str(page_id),"title":title,
                          "pending":pending,"dismissed":dismissed})
    return queue


def page_topic(con, source_id: str, page_id: str) -> dict | None:
    init_db(con)
    row=con.execute("""SELECT t.topic_id,t.canonical_title FROM reference_wiki_topics t
      JOIN reference_wiki_topic_pages p ON p.topic_id=t.topic_id
      WHERE p.source_id=? AND p.page_id=? LIMIT 1""",(source_id,str(page_id))).fetchone()
    if not row: return None
    members=[{"source_id":r[0],"page_id":str(r[1]),"title":r[2],"link_method":r[3]}
             for r in con.execute("""SELECT p.source_id,p.page_id,w.title,p.link_method
               FROM reference_wiki_topic_pages p
               LEFT JOIN reference_wiki_pages w ON w.source_id=p.source_id AND w.page_id=p.page_id
               WHERE p.topic_id=? ORDER BY p.source_id,p.page_id""",(row[0],)).fetchall()]
    return {"topic_id":row[0],"canonical_title":row[1],"members":members}


def search_pages(con, query: str, limit: int = 40) -> list[dict]:
    init_db(con); q=normalize_search(query)
    if not q: return []
    like=f"%{q}%"; found={}

    def add(source,page,title,reason,snippet=None,score=0):
        key=(str(source),str(page))
        row=found.setdefault(key,{"source_id":source,"page_id":str(page),"title":title,"reasons":[],"snippet":snippet,"score":0})
        if reason not in row["reasons"]: row["reasons"].append(reason)
        if snippet and not row.get("snippet"): row["snippet"]=snippet
        row["score"]=max(row["score"],score)

    for r in con.execute("""SELECT source_id,page_id,title FROM reference_wiki_pages
      WHERE lower(title) LIKE ? OR lower(norm_title) LIKE ? LIMIT ?""",(like,like,limit*3)):
        add(*r,"title",score=100 if normalize_search(r[2])==q else 80)
    # BG Wiki's full offline dump is indexed separately; keep it searchable without
    # copying every page into reference_wiki_pages.
    has_bg_index=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='wiki_pages'").fetchone()
    if has_bg_index:
        compact=re.sub(r"[^a-z0-9]","",q)
        for r in con.execute("""SELECT title,url FROM wiki_pages
          WHERE lower(title) LIKE ? OR norm_title LIKE ? LIMIT ?""",(like,f"%{compact}%",limit*3)):
            add("BGWiki",r[0],r[0],"BG index",r[1],75)
    for r in con.execute("""SELECT p.source_id,p.page_id,w.title,t.canonical_title
      FROM reference_wiki_topics t
      JOIN reference_wiki_topic_pages p ON p.topic_id=t.topic_id
      LEFT JOIN reference_wiki_pages w ON w.source_id=p.source_id AND w.page_id=p.page_id
      WHERE t.norm_title LIKE ? LIMIT ?""",(like,limit*3)):
        add(r[0],r[1],r[2] or r[3],"canonical topic",r[3],95)
    for r in con.execute("""SELECT a.source_id,a.page_id,p.title,a.alias FROM reference_wiki_aliases a
      JOIN reference_wiki_pages p ON p.source_id=a.source_id AND p.page_id=a.page_id
      WHERE a.norm_alias LIKE ? LIMIT ?""",(like,limit*3)):
        add(r[0],r[1],r[2],"alias",r[3],90)
    for r in con.execute("""SELECT b.source_id,b.page_id,p.title,b.text FROM reference_wiki_blocks b
      JOIN reference_wiki_pages p ON p.source_id=b.source_id AND p.page_id=b.page_id
      WHERE lower(COALESCE(b.text,'')) LIKE ? LIMIT ?""",(like,limit*3)):
        add(r[0],r[1],r[2],"structured text",(r[3] or "")[:220],55)
    for r in con.execute("""SELECT source_id,page_id,title,page_text FROM reference_wiki_pages
      WHERE lower(COALESCE(page_text,'')) LIKE ? LIMIT ?""",(like,limit*3)):
        add(r[0],r[1],r[2],"page text",(r[3] or "")[:220],35)
    has_tr=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='reference_wiki_translations'").fetchone()
    if has_tr:
        for r in con.execute("""SELECT t.source_id,t.page_id,p.title,t.translated FROM reference_wiki_translations t
          JOIN reference_wiki_pages p ON p.source_id=t.source_id AND p.page_id=t.page_id
          WHERE t.target_lang='en' AND lower(t.translated) LIKE ? LIMIT ?""",(like,limit*3)):
            add(r[0],r[1],r[2],"machine English",(r[3] or "")[:220],65)
    return sorted(found.values(),key=lambda x:(-x["score"],normalize_search(x["title"]),x["source_id"]))[:max(1,min(limit,100))]
