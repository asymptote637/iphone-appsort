// Adapted from Justin Leveck / homescreen-organizer (MIT).
// Copy only synced App.InFocus streams and device metadata into AppSort state.
// No permissions are changed by this helper. No data is sent over the network.
import Foundation
import SQLite3

let fm = FileManager.default
let biome = fm.homeDirectoryForCurrentUser.appendingPathComponent("Library/Biome")
let source = biome.appendingPathComponent("streams/restricted/App.InFocus/remote")
let syncDB = biome.appendingPathComponent("sync/sync.db")

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}
guard CommandLine.arguments.count == 2 else { fail("usage: appsort-usage-helper <state/screentime>") }
let destination = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
guard (try? fm.contentsOfDirectory(atPath: source.path)) != nil else {
    fail("无法读取同步记录。请在系统设置 → 隐私与安全性 → 完全磁盘访问权限中添加 bin/appsort-usage-helper；并确认跨设备共享已开启。")
}
var db: OpaquePointer?
guard sqlite3_open_v2(syncDB.path, &db, SQLITE_OPEN_READONLY, nil) == SQLITE_OK else {
    fail("无法读取同步设备数据库；请检查复制助手的完全磁盘访问权限。")
}
defer { sqlite3_close(db) }
var statement: OpaquePointer?
guard sqlite3_prepare_v2(db, "SELECT * FROM DevicePeer WHERE platform = 2", -1, &statement, nil) == SQLITE_OK else {
    fail("macOS 同步设备数据库格式已变化；无法安全选择 iPhone。")
}
defer { sqlite3_finalize(statement) }
var devices = [[String: Any]]()
while sqlite3_step(statement) == SQLITE_ROW {
    var row = [String: Any]()
    for index in 0..<sqlite3_column_count(statement) {
        let key = String(cString: sqlite3_column_name(statement, index))
        switch sqlite3_column_type(statement, index) {
        case SQLITE_INTEGER: row[key] = sqlite3_column_int64(statement, index)
        case SQLITE_FLOAT: row[key] = sqlite3_column_double(statement, index)
        case SQLITE_TEXT: row[key] = String(cString: sqlite3_column_text(statement, index))
        default: break
        }
    }
    devices.append(row)
}
do {
    try fm.createDirectory(at: destination, withIntermediateDirectories: true)
    let incoming = destination.appendingPathComponent("incoming-" + UUID().uuidString, isDirectory: true)
    try fm.createDirectory(at: incoming, withIntermediateDirectories: true)
    defer { try? fm.removeItem(at: incoming) }
    try fm.copyItem(at: source, to: incoming.appendingPathComponent("App.InFocus"))
    let json = try JSONSerialization.data(withJSONObject: devices, options: [.prettyPrinted, .sortedKeys])
    try json.write(to: incoming.appendingPathComponent("devices.json"), options: .atomic)
    for name in ["App.InFocus", "devices.json"] {
        let target = destination.appendingPathComponent(name)
        if fm.fileExists(atPath: target.path) { try fm.removeItem(at: target) }
        try fm.moveItem(at: incoming.appendingPathComponent(name), to: target)
    }
    try ISO8601DateFormatter().string(from: Date()).write(to: destination.appendingPathComponent("copied-at"), atomically: true, encoding: .utf8)
    print("已复制同步记录及设备清单；未读取其他个人资料。")
} catch {
    fail("复制失败：\(error.localizedDescription)")
}
