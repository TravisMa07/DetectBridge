package io.detectbridge.linux;

import static io.detectbridge.detection.Contracts.check;

import io.detectbridge.transport.Json;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.*;
import java.util.regex.*;
import tools.jackson.databind.JsonNode;

/** Raw audit grammar and independently pinned Linux v6.12 execution policy. */
public final class Audit {
  private static final Pattern HEADER = Pattern.compile(
      "(?:node=([^ ]+) )?type=([A-Z0-9_]+) msg=audit\\(([0-9]+\\.[0-9]{1,9}):([0-9]{1,20})\\):(?: (.*))?");
  private static final Pattern TOKEN = Pattern.compile("([A-Za-z0-9_]+(?:\\[[0-9]+\\])?)=(\"[^\"]*\"|[^ \"]+)(?: |$)");
  private static final Pattern ARG = Pattern.compile("a([0-9]+)(?:\\[([0-9]+)\\]|(_len))?");
  private static final Set<String> TYPES = Set.of("SYSCALL", "EXECVE", "CWD", "PATH", "PROCTITLE", "EOE");
  public record Token(String name, String raw) {}
  public record Record(String type, String timestamp, String serial, String node, List<Token> tokens) {
    public Record { tokens = List.copyOf(tokens); }
    List<String> values(String key) { return tokens.stream().filter(t -> t.name.equals(key)).map(Token::raw).toList(); }
    String one(String key) {
      List<String> values = values(key); check(!values.isEmpty(), "required_slot_missing");
      check(values.size() == 1, "slot_conflict");
      return values.get(0);
    }
  }
  public record Assessment(boolean eligible, List<String> findings, List<String> args,
      Map<String, Object> process, JsonNode fields) {}
  private Audit() {}

  public static Record parse(byte[] bytes) {
    check(bytes.length <= Json.MAX_VALUE, "record_limit");
    String text = Boundary.text(bytes);
    if (text.endsWith("\n")) text = text.substring(0, text.length() - 1);
    check(!text.contains("\n") && !text.contains("\r") && !text.contains("\u0000"), "invalid_framing");
    Matcher head = HEADER.matcher(text); check(head.matches(), "invalid_audit_header");
    occurrence(head.group(3));
    String fields = head.group(5) == null ? "" : head.group(5);
    List<Token> tokens = new ArrayList<>(); Matcher t = TOKEN.matcher(fields); int end = 0;
    while (t.find()) {
      check(t.start() == end && tokens.size() < 4096, "invalid_audit_fields");
      tokens.add(new Token(t.group(1), t.group(2))); end = t.end();
    }
    check(end == fields.length(), "invalid_audit_fields");
    return new Record(head.group(2), head.group(3), head.group(4), head.group(1), tokens);
  }

  static String occurrence(String timestamp) {
    String[] parts = timestamp.split("\\.");
    try {
      Instant time = Instant.ofEpochSecond(Long.parseLong(parts[0]),
          Integer.parseInt((parts[1] + "000000000").substring(0, 9)));
      check(time.toString().matches("[0-9]{4}-.*"), "audit_time_range");
      return time.toString();
    } catch (RuntimeException e) { throw new IllegalArgumentException("invalid_audit_time"); }
  }

  static byte[] decoded(String raw) {
    if (raw.startsWith("\"") && raw.endsWith("\"")) {
      String value = raw.substring(1, raw.length() - 1);
      check(value.chars().allMatch(c -> c >= 0x21 && c <= 0x7e && c != '"'), "invalid_quoted_string");
      return value.getBytes(StandardCharsets.US_ASCII);
    }
    check(raw.matches("(?:[0-9a-fA-F]{2})+"), "invalid_audit_hex");
    return HexFormat.of().parseHex(raw);
  }

  static String string(String raw) {
    String s = Boundary.text(decoded(raw)); check(!s.contains("\u0000"), "nul_scalar"); return s;
  }

  static int number(String raw) {
    check(raw.matches("0|[1-9][0-9]*"), "invalid_decimal");
    try { return Integer.parseInt(raw); }
    catch (NumberFormatException e) { throw new IllegalArgumentException("decimal_limit"); }
  }

  private static boolean execution(Record r) {
    String arch = r.one("arch"), call = r.one("syscall");
    return switch (arch) {
      case "c000003e" -> Set.of("59", "322").contains(call);
      case "40000003" -> Set.of("11", "358").contains(call);
      case "c00000b7" -> Set.of("221", "281").contains(call);
      default -> false;
    };
  }

  public static Assessment assess(List<Record> records) {
    List<String> findings = new ArrayList<>(), args = new ArrayList<>();
    Map<String, Object> process = new LinkedHashMap<>();
    // Retain every token/record in original admission order, including unknown types and duplicates.
    JsonNode fields = Json.MAPPER.valueToTree(Map.of("audit_records", records));
    for (Record r : records) if (!TYPES.contains(r.type)) findings.add("unsupported_type");
    try {
      List<Record> syscalls = records.stream().filter(r -> r.type.equals("SYSCALL")).toList();
      check(!syscalls.isEmpty(), "syscall_missing"); check(syscalls.size() == 1, "syscall_conflict"); Record syscall = syscalls.get(0);
      check(execution(syscall), "unsupported_abi_syscall");
      check(syscall.one("success").equals("yes") && syscall.one("exit").equals("0"), "execution_not_proven");
      String exe = string(syscall.one("exe")); check(!exe.isEmpty(), "executable_missing");
      ((tools.jackson.databind.node.ObjectNode) fields).put("exe", exe);
      process.put("executable", exe); process.put("pid", number(syscall.one("pid")));
      List<Record> cwds = records.stream().filter(r -> r.type.equals("CWD")).toList();
      check(!cwds.isEmpty(), "cwd_missing"); check(cwds.size() == 1, "cwd_conflict"); String cwd = string(cwds.get(0).one("cwd"));
      check(!cwd.isEmpty(), "cwd_missing"); ((tools.jackson.databind.node.ObjectNode) fields).put("cwd", cwd); process.put("working_directory", cwd);
      int items = number(syscall.one("items")); check(items <= 256, "path_count_limit");
      Map<Integer, Record> paths = new TreeMap<>();
      List<Object> decodedPaths = new ArrayList<>();
      for (Record r : records) if (r.type.equals("PATH")) {
        int item = number(r.one("item")); check(paths.putIfAbsent(item, r) == null, "path_conflict");
        // A null/unavailable path remains source evidence and cannot establish completeness.
        decodedPaths.add(Map.of("item", item, "name", string(r.one("name"))));
      }
      ((tools.jackson.databind.node.ObjectNode) fields).set("paths", Json.MAPPER.valueToTree(decodedPaths));
      check(paths.size() == items, "path_count");
      for (int i = 0; i < items; i++) check(paths.containsKey(i), "path_hole");
      Map<Integer, String> whole = new TreeMap<>(), lengths = new TreeMap<>();
      Map<Integer, TreeMap<Integer, String>> fragments = new TreeMap<>();
      List<Integer> counts = new ArrayList<>();
      for (Record r : records) if (r.type.equals("EXECVE")) {
        for (Token token : r.tokens) {
          if (token.name.equals("argc")) { counts.add(number(token.raw)); continue; }
          Matcher m = ARG.matcher(token.name); check(m.matches(), "unsupported_execve_field");
          int index = number(m.group(1)); check(index < 4096, "arg_index_limit");
          if (m.group(2) != null) {
            int f = number(m.group(2)); check(f < 4096, "fragment_limit");
            check(fragments.computeIfAbsent(index, k -> new TreeMap<>()).putIfAbsent(f, token.raw) == null, "fragment_conflict");
          } else check((m.group(3) == null ? whole : lengths).putIfAbsent(index, token.raw) == null, "arg_conflict");
        }
      }
      check(!counts.isEmpty(), "argc_missing"); check(counts.size() == 1, "argc_conflict"); int argc = counts.get(0);
      check(argc <= 4096 && whole.size() + fragments.size() == argc, "argument_count");
      for (int i = 0; i < argc; i++) {
        if (whole.containsKey(i)) {
          check(!fragments.containsKey(i) && !lengths.containsKey(i), "arg_conflict");
          args.add(string(whole.get(i)));
        } else {
          TreeMap<Integer, String> pieces = fragments.get(i);
          check(pieces != null && lengths.containsKey(i), "argument_hole");
          ByteArrayOutputStream bytes = new ByteArrayOutputStream(); int emitted = 0;
          Boolean hex = null;
          for (int f = 0; f < pieces.size(); f++) {
            String piece = pieces.get(f); check(piece != null, "fragment_hole");
            boolean isHex = !piece.startsWith("\"");
            check(hex == null || hex == isHex, "fragment_encoding_conflict"); hex = isHex;
            byte[] data = decoded(piece); bytes.writeBytes(data);
            emitted += isHex ? data.length * 2 : data.length;
          }
          check(number(lengths.get(i)) == emitted, "fragment_length");
          String value = Boundary.text(bytes.toByteArray()); check(!value.contains("\u0000"), "nul_argument"); args.add(value);
        }
      }
      check(lengths.keySet().equals(fragments.keySet()), "orphan_length");
      process.put("args", List.copyOf(args));
      ((tools.jackson.databind.node.ObjectNode) fields).set("arguments", Json.MAPPER.valueToTree(args));
      // More than one EOE is conflicting evidence, even at distinct source positions.
      check(records.stream().filter(r -> r.type.equals("EOE")).count() <= 1, "eoe_conflict");
      check(records.stream().filter(r -> r.type.equals("PROCTITLE")).count() <= 1, "proctitle_conflict");
      for (Record r : records) if (r.type.equals("PROCTITLE")) {
        byte[] original = decoded(r.one("proctitle"));
        ((tools.jackson.databind.node.ObjectNode) fields).put("proctitle_bytes_base64", Base64.getEncoder().encodeToString(original));
      }
    } catch (IllegalArgumentException e) { findings.add(e.getMessage()); }
    return new Assessment(findings.isEmpty(), List.copyOf(findings), List.copyOf(args),
        Map.copyOf(process), fields);
  }
}
