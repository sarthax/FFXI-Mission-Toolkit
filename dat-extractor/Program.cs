// Standalone FFXI dialog-table (.DAT) extractor.
//
// Reimplements the parsing algorithm from POLUtils (https://github.com/Windower/POLUtils)
// PlayOnline.FFXI.FileTypes.DialogTable / Things.DialogTableEntry, transcribed directly rather
// than depending on the original Thing/IThing class hierarchy (which pulls in WinForms/System.Drawing
// for GUI property-page support this tool doesn't need). FFXIEncoding.cs is used unmodified from
// the original project (src/FFXIEncoding.cs) -- it's already a self-contained System.Text.Encoding
// subclass with no GUI dependency.
//
// Usage:
//   dat-extractor <path-to-dat-file> [outputPath.json]        -- extract one file
//   dat-extractor --scan <romRootDir> [--min N] [--contains "text"]  -- scan a whole ROM tree in
//     one process (avoids per-file dotnet-run startup cost), reporting every .DAT that parses as
//     a valid DialogTable. --min filters to files with at least N entries (default 5, cuts out
//     tiny incidental matches). --contains does a case-insensitive substring search across all
//     entries' decoded text and only reports files containing a hit -- the fast way to find which
//     physical .dat holds a specific zone's dialog table.

using System.Text;
using System.Text.Json;
using PlayOnline.FFXI;

if (args.Length >= 1 && args[0] == "--scan")
{
    return ScanTree(args);
}

if (args.Length >= 1 && args[0] == "--resolve")
{
    return ResolveFileNumber(args);
}

if (args.Length >= 1 && args[0] == "--strings")
{
    return DumpStringTable(args);
}

if (args.Length >= 1 && args[0] == "--find-zone")
{
    return FindZone(args);
}

if (args.Length >= 1 && args[0] == "--tree")
{
    return PrintTree(args);
}

if (args.Length >= 1 && args[0] == "--extract-id")
{
    return ExtractById(args);
}

if (args.Length < 1)
{
    Console.Error.WriteLine("Usage: dat-extractor <path-to-dat-file> [output.json]");
    Console.Error.WriteLine("       dat-extractor --scan <romRootDir> [--min N] [--contains \"text\"]");
    return 1;
}

string datPath = args[0];
if (!File.Exists(datPath))
{
    Console.Error.WriteLine($"File not found: {datPath}");
    return 1;
}

using var fs = new FileStream(datPath, FileMode.Open, FileAccess.Read, FileShare.Read);
using var br = new BinaryReader(fs);

var entries = DialogTableParser.Parse(br);

if (entries == null)
{
    Console.Error.WriteLine("Not a recognized DialogTable file (header check failed).");
    return 1;
}

var json = JsonSerializer.Serialize(entries, new JsonSerializerOptions { WriteIndented = true });

if (args.Length >= 2)
{
    File.WriteAllText(args[1], json, Encoding.UTF8);
    Console.Error.WriteLine($"Wrote {entries.Count} entries to {args[1]}");
}
else
{
    Console.WriteLine(json);
}

return 0;

// Transcribed from PlayOnline.FFXI.FFXI.GetFilePath(int, out byte, out short, out byte) -- the
// VTABLE/FTABLE resolver that turns a logical "rom-file id" (as used in POLUtils'
// ROMFileMappings.xml, e.g. the DialogTables category) into a physical ROM<n>/<dir>/<file>.DAT
// path. clientRoot is the FFXI client install dir (the one containing ROM, ROM2, ..., VTABLE.DAT).
static string? ResolveFilePath(string clientRoot, int fileNumber)
{
    for (int i = 1; i < 20; ++i)
    {
        string suffix = i > 1 ? i.ToString() : "";
        string dataDir = i > 1 ? Path.Combine(clientRoot, "ROM" + suffix) : clientRoot;
        string vTableFile = Path.Combine(dataDir, $"VTABLE{suffix}.DAT");
        string fTableFile = Path.Combine(dataDir, $"FTABLE{suffix}.DAT");
        string romDir = i == 1 ? Path.Combine(clientRoot, "ROM") : dataDir;

        if (!File.Exists(vTableFile) || !File.Exists(fTableFile))
        {
            continue;
        }

        try
        {
            using var vfs = new FileStream(vTableFile, FileMode.Open, FileAccess.Read, FileShare.Read);
            using var vbr = new BinaryReader(vfs);
            if (fileNumber >= vbr.BaseStream.Length)
            {
                continue;
            }
            vbr.BaseStream.Seek(fileNumber, SeekOrigin.Begin);
            if (vbr.ReadByte() != i)
            {
                continue;
            }

            using var ffs = new FileStream(fTableFile, FileMode.Open, FileAccess.Read, FileShare.Read);
            using var fbr = new BinaryReader(ffs);
            fbr.BaseStream.Seek(2 * fileNumber, SeekOrigin.Begin);
            ushort fileDir = fbr.ReadUInt16();
            int dir = fileDir / 0x80;
            int file = fileDir % 0x80;
            return Path.Combine(romDir, dir.ToString(), file + ".DAT");
        }
        catch
        {
            continue;
        }
    }
    return null;
}

static int ResolveFileNumber(string[] args)
{
    if (args.Length < 3)
    {
        Console.Error.WriteLine("Usage: dat-extractor --resolve <clientRootDir> <fileNumber> [fileNumber2 ...]");
        return 1;
    }

    string clientRoot = args[1];
    for (int i = 2; i < args.Length; ++i)
    {
        if (!int.TryParse(args[i], out int fileNumber))
        {
            Console.Error.WriteLine($"Skipping non-numeric arg: {args[i]}");
            continue;
        }

        string? path = ResolveFilePath(clientRoot, fileNumber);
        if (path == null)
        {
            Console.WriteLine($"{fileNumber}\t(not found)");
            continue;
        }

        string status = "no file";
        int entryCount = -1;
        if (File.Exists(path))
        {
            try
            {
                using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
                using var br = new BinaryReader(fs);
                var entries = DialogTableParser.Parse(br);
                if (entries != null)
                {
                    status = "DialogTable";
                    entryCount = entries.Count;
                }
                else
                {
                    status = "not a DialogTable";
                }
            }
            catch (Exception ex)
            {
                status = $"error: {ex.Message}";
            }
        }

        Console.WriteLine($"{fileNumber}\t{path}\t{status}\t{entryCount}");
    }

    return 0;
}

static int DumpStringTable(string[] args)
{
    if (args.Length < 2)
    {
        Console.Error.WriteLine("Usage: dat-extractor --strings <path-or-clientRoot> [fileNumber] [--contains \"text\"]");
        Console.Error.WriteLine("  dat-extractor --strings <path.dat>                 -- direct file path");
        Console.Error.WriteLine("  dat-extractor --strings <clientRoot> <fileNumber>  -- resolve by rom-file id first");
        return 1;
    }

    string? containsFilter = null;
    var positional = new List<string>();
    for (int i = 1; i < args.Length; ++i)
    {
        if (args[i] == "--contains" && i + 1 < args.Length)
        {
            containsFilter = args[++i];
        }
        else
        {
            positional.Add(args[i]);
        }
    }

    string path;
    if (positional.Count >= 2 && int.TryParse(positional[1], out int fileNumber))
    {
        string? resolved = ResolveFilePath(positional[0], fileNumber);
        if (resolved == null || !File.Exists(resolved))
        {
            Console.Error.WriteLine($"Could not resolve file number {fileNumber} under {positional[0]}");
            return 1;
        }
        path = resolved;
    }
    else
    {
        path = positional[0];
    }

    if (!File.Exists(path))
    {
        Console.Error.WriteLine($"File not found: {path}");
        return 1;
    }

    using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
    using var br = new BinaryReader(fs);
    var entries = OffsetStringTableParser.Parse(br);

    if (entries == null)
    {
        Console.Error.WriteLine("Not a recognized offset-string-table file (header check failed).");
        return 1;
    }

    foreach (var e in entries)
    {
        if (containsFilter != null && !e.Text.Contains(containsFilter, StringComparison.OrdinalIgnoreCase))
        {
            continue;
        }
        Console.WriteLine($"{e.Index}\t{e.Text}");
    }

    return 0;
}

// "Zone name -> physical dialog-table .dat path" using POLUtils' own ROMFileMappings.xml (the
// same index its DataBrowser dropdowns are built from) plus the AreaName/RegionName string
// tables to resolve the XML's numeric area-name/region-name references into readable text.
static int FindZone(string[] args)
{
    if (args.Length < 3)
    {
        Console.Error.WriteLine("Usage: dat-extractor --find-zone <clientRootDir> <mappingsXmlPath> <zone name substring>");
        return 1;
    }

    string clientRoot = args[1];
    string mappingsPath = args[2];
    string search = string.Join(" ", args.Skip(3));

    if (search.Length == 0)
    {
        Console.Error.WriteLine("Provide a zone name substring to search for.");
        return 1;
    }

    if (!File.Exists(mappingsPath))
    {
        Console.Error.WriteLine($"Mappings file not found: {mappingsPath}");
        return 1;
    }

    // AreaName = string table file 55465, RegionName = 55654 (per FFXIResourceManager.GetAreaName /
    // GetRegionName in the original POLUtils source).
    var areaNames = LoadOffsetStringTableByFileNumber(clientRoot, 55465);
    var regionNames = LoadOffsetStringTableByFileNumber(clientRoot, 55654);

    if (areaNames == null)
    {
        Console.Error.WriteLine("Could not load/resolve the AreaName string table (file 55465) -- can't resolve zone names.");
        return 1;
    }

    var doc = new System.Xml.XmlDocument();
    doc.Load(mappingsPath);

    var dialogTablesCategory = doc.SelectSingleNode("//category[name/i18n-string/@id='Menu:DialogTables']");
    if (dialogTablesCategory == null)
    {
        Console.Error.WriteLine("Could not find the Menu:DialogTables category in the mappings file.");
        return 1;
    }

    int hits = 0;
    foreach (System.Xml.XmlNode romFileNode in dialogTablesCategory.SelectNodes(".//rom-file")!)
    {
        var areaNameNode = romFileNode.SelectSingleNode("area-name");
        if (areaNameNode?.Attributes?["id"] == null)
        {
            continue;
        }
        if (!uint.TryParse(areaNameNode.Attributes["id"]!.Value, out uint areaId))
        {
            continue;
        }
        if (!areaNames.TryGetValue(areaId, out string? areaName) || areaName.Length == 0)
        {
            continue;
        }
        if (!areaName.Contains(search, StringComparison.OrdinalIgnoreCase))
        {
            continue;
        }

        string? romFileIdAttr = romFileNode.Attributes?["id"]?.Value;
        if (romFileIdAttr == null || !int.TryParse(romFileIdAttr, out int romFileId))
        {
            continue;
        }

        // Walk up to the nearest region-name for extra context, if any.
        string regionLabel = "";
        var regionNode = romFileNode.ParentNode?.SelectSingleNode("preceding-sibling::name[1]/region-name")
                          ?? romFileNode.ParentNode?.SelectSingleNode("../name/region-name");
        if (regionNode?.Attributes?["id"] != null && uint.TryParse(regionNode.Attributes["id"]!.Value, out uint regionId)
            && regionNames != null && regionNames.TryGetValue(regionId, out string? rName))
        {
            regionLabel = $" (region: {rName})";
        }

        string? resolvedPath = ResolveFilePath(clientRoot, romFileId);
        ++hits;
        Console.WriteLine($"{areaName}{regionLabel}\trom-file id={romFileId}\t{resolvedPath ?? "(could not resolve to a physical file)"}");
    }

    Console.Error.WriteLine($"Done. {hits} matching zone(s) found.");
    return hits > 0 ? 0 : 1;
}

static Dictionary<uint, string>? LoadOffsetStringTableByFileNumber(string clientRoot, int fileNumber)
{
    string? path = ResolveFilePath(clientRoot, fileNumber);
    if (path == null || !File.Exists(path))
    {
        return null;
    }
    using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
    using var br = new BinaryReader(fs);
    var entries = OffsetStringTableParser.Parse(br);
    if (entries == null)
    {
        return null;
    }
    var dict = new Dictionary<uint, string>();
    foreach (var e in entries)
    {
        dict[e.Index] = e.Text;
    }
    return dict;
}

// Loads either ROMFileMappings.xml or Messages.resx from the embedded copy baked into this
// assembly (see data/ in the project, embedded via the .csproj) -- no external file path needed,
// so the tool works standalone regardless of where a POLUtils checkout (if any) lives on disk.
static System.Xml.XmlDocument LoadEmbeddedXml(string logicalName)
{
    var asm = System.Reflection.Assembly.GetExecutingAssembly();
    using var stream = asm.GetManifestResourceStream(logicalName)
        ?? throw new InvalidOperationException($"Embedded resource not found: {logicalName}");
    var doc = new System.Xml.XmlDocument();
    doc.Load(stream);
    return doc;
}

// Messages.resx labels ("Menu:AreaNames" -> "Area Names") -- WinForms mnemonic markers (&) are
// stripped since they're meaningless outside a menu control.
static Dictionary<string, string> LoadI18nLabels()
{
    var doc = LoadEmbeddedXml("Data.Messages.resx");
    var labels = new Dictionary<string, string>();
    foreach (System.Xml.XmlNode dataNode in doc.SelectNodes("//data")!)
    {
        string? name = dataNode.Attributes?["name"]?.Value;
        string? value = dataNode.SelectSingleNode("value")?.InnerText;
        if (name != null && value != null)
        {
            labels[name] = value.Replace("&", "");
        }
    }
    return labels;
}

// Recursively resolves POLUtils' ROMFileMappings.xml into a labeled tree. i18n-string names come
// from Messages.resx; area-name/region-name numeric references are resolved via the AreaName
// (file 55465) / RegionName (file 55654) string tables when a client root is supplied (pass null
// to browse the category structure without a client -- those labels show as "area-name#N" instead).
static CategoryNode BuildTree(System.Xml.XmlNode rootCategoryNode, Dictionary<string, string> i18n,
    Dictionary<uint, string>? areaNames, Dictionary<uint, string>? regionNames)
{
    string ResolveLabelNode(System.Xml.XmlNode? node, string fallback)
    {
        if (node == null)
        {
            return fallback;
        }
        var i18nNode = node.SelectSingleNode("i18n-string");
        if (i18nNode?.Attributes?["id"] != null)
        {
            return i18n.TryGetValue(i18nNode.Attributes["id"]!.Value, out string? v) ? v : i18nNode.Attributes["id"]!.Value;
        }
        var areaNode = node.SelectSingleNode("area-name");
        if (areaNode?.Attributes?["id"] != null && uint.TryParse(areaNode.Attributes["id"]!.Value, out uint aid))
        {
            return (areaNames != null && areaNames.TryGetValue(aid, out string? an)) ? an : $"area-name#{aid}";
        }
        var regionNode = node.SelectSingleNode("region-name");
        if (regionNode?.Attributes?["id"] != null && uint.TryParse(regionNode.Attributes["id"]!.Value, out uint rid))
        {
            return (regionNames != null && regionNames.TryGetValue(rid, out string? rn)) ? rn : $"region-name#{rid}";
        }
        string text = node.InnerText.Trim();
        return text.Length > 0 ? text : fallback;
    }

    CategoryNode BuildNode(System.Xml.XmlNode node)
    {
        if (node.Name == "rom-file")
        {
            var result = new CategoryNode
            {
                IsLeaf = true,
                RomFileId = int.TryParse(node.Attributes?["id"]?.Value, out int id) ? id : null,
                Label = ResolveLabelNode(node, $"rom-file#{node.Attributes?["id"]?.Value}"),
            };
            return result;
        }
        else // category
        {
            var nameNode = node.SelectSingleNode("name");
            var cat = new CategoryNode { IsLeaf = false, Label = ResolveLabelNode(nameNode, "?") };
            foreach (System.Xml.XmlNode child in node.ChildNodes)
            {
                if (child.Name == "category" || child.Name == "rom-file")
                {
                    cat.Children.Add(BuildNode(child));
                }
            }
            return cat;
        }
    }

    return BuildNode(rootCategoryNode);
}

static int PrintTree(string[] args)
{
    string? clientRoot = null;
    string? search = null;
    for (int i = 1; i < args.Length; ++i)
    {
        if (args[i] == "--client" && i + 1 < args.Length)
        {
            clientRoot = args[++i];
        }
        else
        {
            search = search == null ? args[i] : $"{search} {args[i]}";
        }
    }

    var i18n = LoadI18nLabels();
    Dictionary<uint, string>? areaNames = null;
    Dictionary<uint, string>? regionNames = null;
    if (clientRoot != null)
    {
        areaNames = LoadOffsetStringTableByFileNumber(clientRoot, 55465);
        regionNames = LoadOffsetStringTableByFileNumber(clientRoot, 55654);
    }

    var mappingsDoc = LoadEmbeddedXml("Data.ROMFileMappings.xml");
    var root = mappingsDoc.SelectSingleNode("/rom-file-mappings")!;
    var topCategories = new List<CategoryNode>();
    foreach (System.Xml.XmlNode child in root.ChildNodes)
    {
        if (child.Name == "category")
        {
            topCategories.Add(BuildTree(child, i18n, areaNames, regionNames));
        }
    }

    void PrintNode(CategoryNode node, string path, bool onlyMatches)
    {
        string fullPath = path.Length == 0 ? node.Label : $"{path} > {node.Label}";
        bool selfMatches = search == null || node.Label.Contains(search, StringComparison.OrdinalIgnoreCase);

        if (node.IsLeaf)
        {
            if (onlyMatches || selfMatches)
            {
                Console.WriteLine($"{fullPath}\trom-file id={node.RomFileId}");
            }
            return;
        }

        // A category matches (and prints all children) if its own label matches; otherwise
        // recurse and only print children that themselves match (or contain matches).
        foreach (var child in node.Children)
        {
            PrintNode(child, fullPath, onlyMatches || selfMatches);
        }
    }

    foreach (var top in topCategories)
    {
        PrintNode(top, "", false);
    }

    return 0;
}

static int ExtractById(string[] args)
{
    if (args.Length < 3)
    {
        Console.Error.WriteLine("Usage: dat-extractor --extract-id <clientRootDir> <romFileId> [output.json]");
        return 1;
    }

    string clientRoot = args[1];
    if (!int.TryParse(args[2], out int romFileId))
    {
        Console.Error.WriteLine($"Not a valid rom-file id: {args[2]}");
        return 1;
    }

    string? path = ResolveFilePath(clientRoot, romFileId);
    if (path == null || !File.Exists(path))
    {
        Console.Error.WriteLine($"Could not resolve rom-file id {romFileId} to a physical file.");
        return 1;
    }

    using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
    using var br = new BinaryReader(fs);

    // Auto-detect: try each supported format in turn, since there's no reliable way to know
    // which one a given rom-file id uses ahead of time without just trying. DmsgStringTable is
    // deliberately checked before OffsetStringTable -- OffsetStringTable's header check is purely
    // arithmetic (byte counts adding up) and produced a real false-positive (0 entries on a valid
    // 41KB Missions file) against a d_msg-format file before this reordering; DmsgStringTable's
    // "d_msg" magic-string check is a much safer positive signal, so it goes first.
    List<DialogEntry>? entries = DialogTableParser.Parse(br);
    string format = "DialogTable";
    if (entries == null)
    {
        fs.Position = 0;
        entries = DmsgStringTableParser.Parse(br);
        format = "DmsgStringTable";
    }
    if (entries == null)
    {
        fs.Position = 0;
        entries = XiStringTableParser.Parse(br);
        format = "XiStringTable";
    }
    if (entries == null)
    {
        fs.Position = 0;
        entries = OffsetStringTableParser.Parse(br);
        format = "OffsetStringTable";
    }
    if (entries == null)
    {
        fs.Position = 0;
        entries = MobListParser.Parse(br);
        format = "MobList";
    }
    if (entries == null)
    {
        fs.Position = 0;
        entries = ItemDataParser.Parse(br);
        format = "ItemData";
    }

    if (entries == null)
    {
        Console.Error.WriteLine($"{path}: not a recognized format (DialogTable, DmsgStringTable, OffsetStringTable, MobList, ItemData all rejected -- Images and other categories still aren't ported).");
        return 1;
    }

    Console.Error.WriteLine($"{path} ({format}, {entries.Count} entries)");
    var json = JsonSerializer.Serialize(entries, new JsonSerializerOptions { WriteIndented = true });
    if (args.Length >= 4)
    {
        File.WriteAllText(args[3], json, Encoding.UTF8);
        Console.Error.WriteLine($"Wrote to {args[3]}");
    }
    else
    {
        Console.WriteLine(json);
    }

    return 0;
}

static int ScanTree(string[] args)
{
    if (args.Length < 2)
    {
        Console.Error.WriteLine("Usage: dat-extractor --scan <romRootDir> [--min N] [--contains \"text\"]");
        return 1;
    }

    string root = args[1];
    int minEntries = 5;
    string? containsFilter = null;

    for (int i = 2; i < args.Length; ++i)
    {
        if (args[i] == "--min" && i + 1 < args.Length)
        {
            minEntries = int.Parse(args[++i]);
        }
        else if (args[i] == "--contains" && i + 1 < args.Length)
        {
            containsFilter = args[++i];
        }
    }

    if (!Directory.Exists(root))
    {
        Console.Error.WriteLine($"Directory not found: {root}");
        return 1;
    }

    int scanned = 0;
    int hits = 0;
    foreach (var path in Directory.EnumerateFiles(root, "*.DAT", SearchOption.AllDirectories))
    {
        ++scanned;
        if (scanned % 2000 == 0)
        {
            Console.Error.WriteLine($"...scanned {scanned}, {hits} hits so far ({path})");
        }

        List<DialogEntry>? entries;
        try
        {
            using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
            using var br = new BinaryReader(fs);
            entries = DialogTableParser.Parse(br);
        }
        catch
        {
            continue;
        }

        if (entries == null || entries.Count < minEntries)
        {
            continue;
        }

        if (containsFilter != null)
        {
            bool match = entries.Any(e => e.Text.Contains(containsFilter, StringComparison.OrdinalIgnoreCase));
            if (!match)
            {
                continue;
            }
        }

        ++hits;
        Console.WriteLine($"{path}\t{entries.Count} entries");
        if (containsFilter != null)
        {
            foreach (var e in entries.Where(e => e.Text.Contains(containsFilter, StringComparison.OrdinalIgnoreCase)))
            {
                Console.WriteLine($"    [{e.Index}] {e.Text.Replace("\r\n", " / ")}");
            }
        }
    }

    Console.Error.WriteLine($"Done. Scanned {scanned} files, {hits} dialog-table matches.");
    return 0;
}

public record DialogEntry(uint Index, string Text);

public static class DialogTableParser
{
    // Transcribed from PlayOnline.FFXI.FileTypes.DialogTable.Load -- see POLUtils-reference for
    // the original. Determines the entry count/offsets from the file header, then reads each
    // entry's raw bytes via DialogTableEntry equivalent below.
    public static List<DialogEntry>? Parse(BinaryReader br)
    {
        if (br.BaseStream.Length < 4)
        {
            return null;
        }

        uint fileSizeMaybe = br.ReadUInt32();
        if (fileSizeMaybe != (0x10000000 + br.BaseStream.Length - 4))
        {
            return null;
        }

        uint firstTextPos = br.ReadUInt32() ^ 0x80808080;
        if ((firstTextPos % 4) != 0 || firstTextPos > br.BaseStream.Length || firstTextPos < 8)
        {
            return null;
        }

        uint entryCount = firstTextPos / 4;

        // Entries aren't always sequential in the file, so collect + sort the offsets first
        // (matches the original's approach -- entry length is derived from the gap to the next
        // offset, so they need to be in file order regardless of logical index order).
        var offsets = new List<uint>((int)entryCount + 1) { firstTextPos };
        for (int i = 1; i < entryCount; ++i)
        {
            offsets.Add(br.ReadUInt32() ^ 0x80808080);
        }
        offsets.Add((uint)br.BaseStream.Length - 4);
        offsets.Sort();

        var results = new List<DialogEntry>((int)entryCount);
        for (uint i = 0; i < entryCount; ++i)
        {
            long start = offsets[(int)i];
            long end = offsets[(int)i + 1];
            if (start < 4 * entryCount || 4 + start >= br.BaseStream.Length)
            {
                return null; // matches original: whole file treated as unparseable on any bad entry
            }

            string? text = ReadEntryText(br, start, end);
            if (text == null)
            {
                return null;
            }

            results.Add(new DialogEntry(i, text));
        }

        return results;
    }

    // Transcribed from PlayOnline.FFXI.Things.DialogTableEntry.Read. Decodes one entry's raw
    // bytes into text, expanding the same in-band control codes (line breaks, name/parameter
    // placeholders, prompts, etc.) that produce the "<Speaker Name>"-style markers seen in
    // POLUtils' own DialogTableEntry XML exports.
    private static string? ReadEntryText(BinaryReader br, long entryStart, long entryEnd)
    {
        try
        {
            br.BaseStream.Seek(4 + entryStart, SeekOrigin.Begin);
            byte[] textBytes = br.ReadBytes((int)(entryEnd - entryStart));
            for (int i = 0; i < textBytes.Length; ++i)
            {
                textBytes[i] ^= 0x80; // matches original's "evil encryption-breaking" XOR
            }

            var text = new StringBuilder();
            var enc = new FFXIEncoding();
            int lastPos = 0;
            char ms = FFXIEncoding.SpecialMarkerStart;
            char me = FFXIEncoding.SpecialMarkerEnd;

            for (int i = 0; i < textBytes.Length; ++i)
            {
                byte b = textBytes[i];
                if (b == 0x07)
                {
                    if (lastPos < i) text.Append(enc.GetString(textBytes, lastPos, i - lastPos));
                    text.Append("\r\n");
                    lastPos = i + 1;
                }
                else if (b == 0x08)
                {
                    if (lastPos < i) text.Append(enc.GetString(textBytes, lastPos, i - lastPos));
                    text.Append($"{ms}Player Name{me}");
                    lastPos = i + 1;
                }
                else if (b == 0x09)
                {
                    if (lastPos < i) text.Append(enc.GetString(textBytes, lastPos, i - lastPos));
                    text.Append($"{ms}Speaker Name{me}");
                    lastPos = i + 1;
                }
                else if (b == 0x0a && i + 1 < textBytes.Length)
                {
                    if (lastPos < i) text.Append(enc.GetString(textBytes, lastPos, i - lastPos));
                    text.Append($"{ms}Numeric Parameter {textBytes[i + 1]}{me}");
                    lastPos = i + 2;
                    ++i;
                }
                else if (b == 0x0b)
                {
                    if (lastPos < i) text.Append(enc.GetString(textBytes, lastPos, i - lastPos));
                    text.Append($"{ms}Selection Dialog{me}");
                    lastPos = i + 1;
                }
                else if (b == 0x0c && i + 1 < textBytes.Length)
                {
                    if (lastPos < i) text.Append(enc.GetString(textBytes, lastPos, i - lastPos));
                    text.Append($"{ms}Multiple Choice (Parameter {textBytes[i + 1]}){me}");
                    lastPos = i + 2;
                    ++i;
                }
                else if (b == 0x19 && i + 1 < textBytes.Length)
                {
                    if (lastPos < i) text.Append(enc.GetString(textBytes, lastPos, i - lastPos));
                    text.Append($"{ms}Item Parameter {textBytes[i + 1]}{me}");
                    lastPos = i + 2;
                    ++i;
                }
                else if (b == 0x1a && i + 1 < textBytes.Length)
                {
                    if (lastPos < i) text.Append(enc.GetString(textBytes, lastPos, i - lastPos));
                    text.Append($"{ms}Key Item Parameter {textBytes[i + 1]}{me}");
                    lastPos = i + 2;
                    ++i;
                }
                else if (b == 0x1c && i + 1 < textBytes.Length)
                {
                    if (lastPos < i) text.Append(enc.GetString(textBytes, lastPos, i - lastPos));
                    text.Append($"{ms}Player/Chocobo Parameter {textBytes[i + 1]}{me}");
                    lastPos = i + 2;
                    ++i;
                }
                else if (b == 0x1e && i + 1 < textBytes.Length)
                {
                    if (lastPos < i) text.Append(enc.GetString(textBytes, lastPos, i - lastPos));
                    text.Append($"{ms}Set Color #{textBytes[i + 1]}{me}");
                    lastPos = i + 2;
                    ++i;
                }
                else if (b == 0x7f && i + 1 < textBytes.Length)
                {
                    if (lastPos < i) text.Append(enc.GetString(textBytes, lastPos, i - lastPos));
                    if (textBytes[i + 1] == 0x31 && i + 2 < textBytes.Length)
                    {
                        if (textBytes[i + 2] != 0)
                        {
                            text.Append($"{ms}{textBytes[i + 2]}-Second Delay + Prompt{me}");
                        }
                        else
                        {
                            text.Append($"{ms}Prompt{me}");
                        }
                        ++lastPos;
                        ++i;
                    }
                    else if (textBytes[i + 1] == 0x85)
                    {
                        text.Append($"{ms}Multiple Choice (Player Gender){me}");
                    }
                    else if (textBytes[i + 1] == 0x8D && i + 2 < textBytes.Length)
                    {
                        text.Append($"{ms}Weather Event Parameter {textBytes[i + 2]}{me}");
                        ++lastPos;
                        ++i;
                    }
                    else if (textBytes[i + 1] == 0x8E && i + 2 < textBytes.Length)
                    {
                        text.Append($"{ms}Weather Type Parameter {textBytes[i + 2]}{me}");
                        ++lastPos;
                        ++i;
                    }
                    else if (textBytes[i + 1] == 0x92 && i + 2 < textBytes.Length)
                    {
                        text.Append($"{ms}Singular/Plural Choice (Parameter {textBytes[i + 2]}){me}");
                        ++lastPos;
                        ++i;
                    }
                    else if (textBytes[i + 1] == 0xB1 && i + 2 < textBytes.Length)
                    {
                        text.Append($"{ms}Title Parameter {textBytes[i + 2]}{me}");
                        ++lastPos;
                        ++i;
                    }
                    else if (i + 2 < textBytes.Length)
                    {
                        text.Append($"{ms}Unknown Parameter (Type: {textBytes[i + 1]:X2}) {textBytes[i + 2]}{me}");
                        ++lastPos;
                        ++i;
                    }
                    else
                    {
                        text.Append($"{ms}Unknown Marker Type: {textBytes[i + 1]:X2}{me}");
                    }
                    lastPos = i + 2;
                    ++i;
                }
                else if (b == 0x7f || b < 0x20)
                {
                    if (lastPos < i) text.Append(enc.GetString(textBytes, lastPos, i - lastPos));
                    text.Append($"{ms}Possible Special Code: {b:X2}{me}");
                    lastPos = i + 1;
                }
            }

            if (lastPos < textBytes.Length)
            {
                text.Append(enc.GetString(textBytes, lastPos, textBytes.Length - lastPos));
            }

            return text.ToString().TrimEnd('\0');
        }
        catch
        {
            return null;
        }
    }
}

// Transcribed from PlayOnline.FFXI.FFXIResourceManager.GetStringTableEntry -- the format used by
// GetAreaName/GetJobName/GetRegionName (file numbers 55465/55467/55654). Not the same format as
// either SimpleStringTable.cs or XIStringTable.cs in the original project -- this one has an 8-byte
// (offset,length) descriptor per entry at 0x40, with offset/length XORed by 0xFFFFFFFF and text
// XORed by 0xFF, distinct from DialogTable's XOR-0x80 scheme. Extended here to read every entry
// (the original only reads one entry by ID at a time, since that's all FFXIResourceManager needed).
public static class OffsetStringTableParser
{
    public static List<DialogEntry>? Parse(BinaryReader br)
    {
        if (br.BaseStream.Length < 0x18 + 16)
        {
            return null;
        }

        br.BaseStream.Position = 0x18;
        uint headerBytes = br.ReadUInt32();
        uint entryBytes = br.ReadUInt32();
        br.ReadUInt32(); // unknown
        uint dataBytes = br.ReadUInt32();

        if (headerBytes != 0x40 || headerBytes + entryBytes + dataBytes != br.BaseStream.Length)
        {
            return null;
        }

        uint entryCount = entryBytes / 8;
        var results = new List<DialogEntry>((int)entryCount);
        var enc = new FFXIEncoding();

        for (uint id = 0; id < entryCount; ++id)
        {
            br.BaseStream.Position = 0x40 + id * 8;
            uint offset = br.ReadUInt32() ^ 0xFFFFFFFF;
            uint length = (br.ReadUInt32() ^ 0xFFFFFFFF) - 40;

            if (40 + offset + length > dataBytes)
            {
                continue; // matches original's bounds check -- skip malformed entries rather than aborting
            }

            br.BaseStream.Position = headerBytes + entryBytes + 40 + offset;
            byte[] textBytes = br.ReadBytes((int)length);
            for (int i = 0; i < textBytes.Length; ++i)
            {
                textBytes[i] ^= 0xff;
            }
            string text = enc.GetString(textBytes).TrimEnd('\0');
            results.Add(new DialogEntry(id, text));
        }

        return results;
    }
}

public class CategoryNode
{
    public string Label = "";
    public bool IsLeaf;
    public int? RomFileId;
    public List<CategoryNode> Children = new();
}

// Transcribed from PlayOnline.FFXI.FileTypes.MobList / Things.MobListEntry -- fixed 0x20-byte
// records (0x1C-byte name + 4-byte id). ID encodes zone: 0x01<zone><mobid> normally, or
// 0x013<zone><mobid> / 0x011<zone><mobid> for special "instanced" zones (MMM, Meebles). Entire
// file is always for one zone.
public static class MobListParser
{
    public static List<DialogEntry>? Parse(BinaryReader br)
    {
        if (br.BaseStream.Length % 0x20 != 0 || br.BaseStream.Length == 0)
        {
            return null;
        }

        long entryCount = br.BaseStream.Length / 0x20;
        var results = new List<DialogEntry>((int)entryCount);
        var enc = new FFXIEncoding();
        uint zoneMask = 0;

        for (int i = 0; i < entryCount; ++i)
        {
            byte[] nameBytes = br.ReadBytes(0x1C);
            uint id = br.ReadUInt32();

            if (id != 0)
            {
                uint idZoneBits = id & 0xFFF00000;
                if (idZoneBits != 0x01000000 && idZoneBits != 0x01300000 && idZoneBits != 0x01100000)
                {
                    return null; // not a real mob list
                }
            }

            if (i == 0)
            {
                string firstName = enc.GetString(nameBytes).TrimEnd('\0');
                if (id != 0 || firstName != "none")
                {
                    return null;
                }
            }
            else if (id != 0)
            {
                uint thisZone = id & 0x000FF000;
                if (zoneMask == 0)
                {
                    zoneMask = thisZone;
                }
                else if (thisZone != zoneMask)
                {
                    return null; // mixed zones -- not a valid single mob list file
                }
            }

            string name = enc.GetString(nameBytes).TrimEnd('\0');
            results.Add(new DialogEntry(id, name));
        }

        return results;
    }
}

// Transcribed from PlayOnline.FFXI.Things.Item / FileTypes.ItemData / FFXIEncryption.Rotate.
// Item DATs are fixed 0xC00-byte records, XOR-free but bit-rotated (right-rotate by 5 bits) --
// distinct from every other format in this tool, none of which use this obfuscation. Only
// extracts id + name (the most commonly needed fields for cross-referencing Lua item IDs against
// real names) -- the full format also encodes level/jobs/races/damage/etc. per equipment slot,
// not ported here. See NOTICE.md; this is a straight port of POLUtils' Item.Read()/DeduceType(),
// with all Icon/PropertyPage/stat-field handling stripped since they're not needed for id+name.
public static class ItemDataParser
{
    private enum ItemKind { Unknown, Item, UsableItem, PuppetItem, Armor, Weapon, Slip, Instinct, Monipulator, Currency }

    private static void RotateRight5(byte[] data)
    {
        for (int i = 0; i < data.Length; ++i)
        {
            data[i] = (byte)((data[i] >> 5) | (data[i] << (8 - 5)));
        }
    }

    private static ItemKind DeduceType(uint id)
    {
        if (id == 0xffff) return ItemKind.Currency;
        if (id < 0x1000) return ItemKind.Item;
        if (id < 0x2000) return ItemKind.UsableItem;
        if (id < 0x2200) return ItemKind.PuppetItem;
        if (id < 0x2800) return ItemKind.Item;
        if (id < 0x4000) return ItemKind.Armor;
        if (id < 0x5A00) return ItemKind.Weapon;
        if (id < 0x7000) return ItemKind.Armor;
        if (id < 0x7400) return ItemKind.Slip;
        if (id < 0x7800) return ItemKind.Instinct;
        if (id < 0xF200) return ItemKind.Monipulator;
        return ItemKind.Unknown;
    }

    // Bytes to skip after the 14-byte common header (id/flags/stacksize/type/resourceid/
    // validtargets) to reach the string table -- matches the exact field lists in the original
    // Item.Read()'s per-type branches, just counted rather than parsed since only name is needed.
    private static int ExtraFieldBytes(ItemKind kind) => kind switch
    {
        ItemKind.Armor => 30,
        ItemKind.Weapon => 42,
        ItemKind.PuppetItem => 10,
        ItemKind.Instinct => 26,
        ItemKind.Item => 10,
        ItemKind.UsableItem => 14,
        ItemKind.Currency => 2,
        ItemKind.Slip => 70,
        ItemKind.Monipulator => 98,
        _ => -1,
    };

    private static string? ReadItemString(BinaryReader br, FFXIEncoding enc)
    {
        if (br.ReadUInt32() != 1)
        {
            return null;
        }
        for (int i = 0; i < 6; ++i)
        {
            if (br.ReadUInt32() != 0)
            {
                return null;
            }
        }
        var textBytes = new List<byte>();
        while (br.BaseStream.Position < 0x280)
        {
            byte[] next4 = br.ReadBytes(4);
            int usable = next4.Length;
            while (usable > 0 && next4[usable - 1] == 0)
            {
                --usable;
            }
            if (usable != 4)
            {
                for (int i = 0; i < usable; ++i)
                {
                    textBytes.Add(next4[i]);
                }
                return enc.GetString(textBytes.ToArray());
            }
            textBytes.AddRange(next4);
        }
        return null;
    }

    public static List<DialogEntry>? Parse(BinaryReader br)
    {
        if (br.BaseStream.Length % 0xC00 != 0 || br.BaseStream.Length < 0xC000)
        {
            return null;
        }

        // DeduceType: peek the first 4 (rotated) bytes of the first record only -- the whole
        // file shares one type.
        br.BaseStream.Position = 0;
        byte[] peek = br.ReadBytes(4);
        RotateRight5(peek);
        var kind = DeduceType(BitConverter.ToUInt32(peek, 0));
        int extraBytes = ExtraFieldBytes(kind);
        if (kind == ItemKind.Unknown || extraBytes < 0)
        {
            return null;
        }

        br.BaseStream.Position = 0;
        long recordCount = br.BaseStream.Length / 0xC00;
        var results = new List<DialogEntry>((int)recordCount);
        var enc = new FFXIEncoding();

        for (long i = 0; i < recordCount; ++i)
        {
            byte[] record = br.ReadBytes(0xC00);
            RotateRight5(record);
            using var ms = new MemoryStream(record, false);
            using var rbr = new BinaryReader(ms);

            uint id = rbr.ReadUInt32();
            rbr.ReadUInt16(); // flags
            rbr.ReadUInt16(); // stack size
            rbr.ReadUInt16(); // item type (sub-type, not needed for name lookup)
            rbr.ReadUInt16(); // resource id
            rbr.ReadUInt16(); // valid targets
            rbr.BaseStream.Position += extraBytes;

            long stringBase = rbr.BaseStream.Position;
            uint stringCount = rbr.ReadUInt32();
            if (stringCount == 0 || stringCount > 9)
            {
                if (record.Length == 0xC000 && kind == ItemKind.Currency && i > 0)
                {
                    break; // matches original: currency DATs have 1 real item + 15 padding entries
                }
                continue;
            }

            string? name = null;
            for (uint s = 0; s < stringCount; ++s)
            {
                long offset = stringBase + rbr.ReadUInt32();
                uint flag = rbr.ReadUInt32();
                if (offset < 0 || offset + 0x20 > 0x280 || (flag != 0 && flag != 1))
                {
                    name = null;
                    break;
                }
                if (flag == 0)
                {
                    long resumePos = stringBase + 4 + 8 * (s + 1);
                    rbr.BaseStream.Position = offset;
                    string? text = ReadItemString(rbr, enc);
                    if (s == 0)
                    {
                        name = text;
                    }
                    rbr.BaseStream.Position = resumePos;
                }
            }

            if (name != null)
            {
                results.Add(new DialogEntry(id, name));
            }
        }

        return results.Count > 0 ? results : null;
    }
}

// Transcribed from PlayOnline.FFXI.FileTypes.DMSGStringTable3 / Things.DMSGStringBlock -- a
// third, distinct string-table format (magic header "d_msg"), used for the Missions/Quests text
// categories, not the same layout as OffsetStringTableParser (which covers Area/Region/Job
// Names). POLUtils actually has three "d_msg" variants (DMSGStringTable/2/3); this data uses
// variant 3 specifically -- confirmed by manually walking a real 41KB Missions file byte-by-byte
// against all three header layouts (variant 1's header didn't match at all; variant 2's did until
// a "must be 0" check failed; variant 3's matched cleanly end-to-end, with EntryCount=64 *
// BytesPerEntry=640 == DataBytes=40960, and HeaderBytes=64 + DataBytes=40960 == the real
// FileSize=41024). Found this after OffsetStringTableParser produced a false-positive 0-entry
// match on the same file -- its check is purely arithmetic and happened to pass by coincidence.
// Each entry (a DMSGStringBlock) can hold multiple localized/pluralized strings (up to 15 in the
// original); this only keeps the first non-null one, matching DMSGStringBlock.ToString()'s own
// behavior in POLUtils.
public static class DmsgStringTableParser
{
    public static List<DialogEntry>? Parse(BinaryReader br)
    {
        if (br.BaseStream.Length < 0x40)
        {
            return null;
        }

        var enc = new FFXIEncoding();
        br.BaseStream.Position = 0;

        if (enc.GetString(br.ReadBytes(8)) != "d_msg".PadRight(8, '\0'))
        {
            return null;
        }
        ushort flag1 = br.ReadUInt16();
        if (flag1 != 0 && flag1 != 1)
        {
            return null;
        }
        ushort flag2 = br.ReadUInt16();
        if (flag2 != 0 && flag2 != 1)
        {
            return null;
        }
        if (br.ReadUInt32() != 3 || br.ReadUInt32() != 3)
        {
            return null;
        }
        uint fileSize = br.ReadUInt32();
        if (fileSize != br.BaseStream.Length)
        {
            return null;
        }
        uint headerBytes = br.ReadUInt32();
        if (headerBytes != 0x40)
        {
            return null;
        }
        if (br.ReadUInt32() != 0)
        {
            return null;
        }
        int bytesPerEntry = br.ReadInt32();
        if (bytesPerEntry < 0)
        {
            return null;
        }
        uint dataBytes = br.ReadUInt32();
        if (fileSize != headerBytes + dataBytes || bytesPerEntry == 0 || dataBytes % bytesPerEntry != 0)
        {
            return null;
        }
        uint entryCount = br.ReadUInt32();
        if (entryCount * bytesPerEntry != dataBytes)
        {
            return null;
        }
        if (br.ReadUInt32() != 1 || br.ReadUInt64() != 0 || br.ReadUInt64() != 0)
        {
            return null;
        }

        var results = new List<DialogEntry>((int)entryCount);
        for (uint i = 0; i < entryCount; ++i)
        {
            byte[] blockBytes = br.ReadBytes(bytesPerEntry);
            using var ms = new MemoryStream(blockBytes, false);
            using var ebr = new BinaryReader(ms);

            string? text = ReadStringBlock(ebr, enc);
            if (text == null)
            {
                return null;
            }
            results.Add(new DialogEntry(i, text));
        }

        return results;
    }

    // Transcribed from Things.DMSGStringBlock.Read -- returns the first non-null string in the
    // block (matching DMSGStringBlock.ToString()'s own fallback behavior), not all of them.
    private static string? ReadStringBlock(BinaryReader br, FFXIEncoding enc)
    {
        bool needBitFlip = false;
        int stringCount = br.ReadInt32();
        if (stringCount < 0 || stringCount > 100)
        {
            stringCount = ~stringCount;
            if (stringCount < 0 || stringCount > 100)
            {
                return null;
            }
            needBitFlip = true;
        }

        var offsets = new uint[stringCount];
        var flags = new uint[stringCount];
        for (int i = 0; i < stringCount; ++i)
        {
            offsets[i] = br.ReadUInt32() ^ (needBitFlip ? 0xffffffffu : 0u);
            flags[i] = br.ReadUInt32() ^ (needBitFlip ? 0xffffffffu : 0u);
            if (offsets[i] + 28 + 4 > br.BaseStream.Length || (flags[i] != 0 && flags[i] != 1))
            {
                return null;
            }
        }

        string? firstString = null;
        for (int i = 0; i < stringCount; ++i)
        {
            br.BaseStream.Position = 28 + offsets[i];
            var textBytes = new List<byte>();
            while (true)
            {
                byte[] four = br.ReadBytes(4);
                if (four.Length < 4)
                {
                    return null;
                }
                if (needBitFlip)
                {
                    four[0] ^= 0xff;
                    four[1] ^= 0xff;
                    four[2] ^= 0xff;
                    four[3] ^= 0xff;
                }
                textBytes.AddRange(four);
                if (four[3] == 0)
                {
                    break;
                }
            }
            string s = enc.GetString(textBytes.ToArray()).TrimEnd('\0');
            if (firstString == null && s.Length > 0)
            {
                firstString = s;
            }
        }

        return firstString ?? "";
    }
}

// Transcribed from PlayOnline.FFXI.FileTypes.XIStringTable / Things.XIStringTableEntry -- a
// fourth string-table format (magic header "XISTRING"), distinct from OffsetStringTable (Area/
// Region/Job Names) and DmsgStringTable (Missions/Quests). Covers "Time-Related Terms +
// Pronouns", "In-Game Messages (2)", and "POL Messages" -- confirmed by matching this exact
// magic string in all three files' headers.
public static class XiStringTableParser
{
    public static List<DialogEntry>? Parse(BinaryReader br)
    {
        if (br.BaseStream.Length < 0x38)
        {
            return null;
        }

        var enc = new FFXIEncoding();
        br.BaseStream.Position = 0;

        if (enc.GetString(br.ReadBytes(10)) != "XISTRING".PadRight(10, '\0'))
        {
            return null;
        }
        if (br.ReadUInt16() != 2)
        {
            return null;
        }
        foreach (byte b in br.ReadBytes(20))
        {
            if (b != 0)
            {
                return null;
            }
        }

        uint fileSize = br.ReadUInt32();
        if (fileSize != br.BaseStream.Length)
        {
            return null;
        }
        uint entryCount = br.ReadUInt32();
        uint entryBytes = br.ReadUInt32();
        uint dataBytes = br.ReadUInt32();
        br.ReadUInt32(); // unknown
        br.ReadUInt32(); // unknown
        if (entryBytes != entryCount * 12 || fileSize != 0x38 + entryBytes + dataBytes)
        {
            return null;
        }

        var results = new List<DialogEntry>((int)entryCount);
        for (uint i = 0; i < entryCount; ++i)
        {
            br.BaseStream.Seek(0x38 + 12 * i, SeekOrigin.Begin);
            uint offset = br.ReadUInt32();
            short size = br.ReadInt16();
            br.BaseStream.Position += 6; // unknown fields

            if (size < 0 || offset + size > dataBytes)
            {
                return null;
            }

            br.BaseStream.Seek(0x38 + entryBytes + offset, SeekOrigin.Begin);
            string text = enc.GetString(br.ReadBytes(size)).TrimEnd('\0');
            results.Add(new DialogEntry(i, text));
        }

        return results;
    }
}
