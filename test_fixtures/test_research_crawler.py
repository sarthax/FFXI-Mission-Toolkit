#!/usr/bin/env python3
import tempfile
from pathlib import Path

from workbench.research.crawler import BoundedSourceCrawler, CrawlPolicy


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)/"src"
        outside=Path(td)/"outside.txt"
        (root/"scripts").mkdir(parents=True)
        (root/"scripts"/"mission.lua").write_text(
            "function onEventFinish(player)\n  player:getID()\nend\n",
            encoding="utf-8",
        )
        (root/"secret.key").write_text("do-not-read",encoding="utf-8")
        (root/"binary.bin").write_bytes(b"abc")
        outside.write_text("outside",encoding="utf-8")

        crawler=BoundedSourceCrawler(CrawlPolicy(
            roots=(root,),
            max_files=10,
            max_total_bytes=10000,
            max_file_bytes=5000,
        ))

        found=crawler.search("getID")
        assert found["status"]=="OK",found
        assert len(found["matches"])==1,found
        assert found["matches"][0]["path"]=="scripts/mission.lua",found

        read=crawler.read("scripts/mission.lua")
        assert read["status"]=="OK",read
        assert "getID" in read["content"],read

        blocked=crawler.read("secret.key")
        assert blocked["status"]=="DENIED",blocked

        outside_result=crawler.read(str(outside))
        assert outside_result["status"]=="DENIED",outside_result

        files=[rel.as_posix() for _root,rel,_path in crawler.iter_files()]
        assert "scripts/mission.lua" in files,files
        assert "secret.key" not in files,files
        assert "binary.bin" not in files,files

    print("bounded research source crawler self-test: PASS")


if __name__=="__main__":
    main()
