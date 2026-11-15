package io.detectbridge.linux;

import static io.detectbridge.detection.Contracts.check;

import io.detectbridge.transport.Json;
import java.net.InetAddress;
import java.time.OffsetDateTime;
import java.util.*;
import java.util.regex.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** Exact English OpenSSH 9.x password grammar inside RFC5424 version 1. */
public final class OpenSsh {
  private static final Pattern HEADER = Pattern.compile(
      "<([0-9]{1,3})>1 ([^ ]+) ([!-~]{1,255}) ([!-~]{1,48}) ([!-~]{1,128}) ([!-~]{1,32}) (.*)");
  private static final Pattern BODY = Pattern.compile(
      "(Accepted|Failed) password for ([^ \\r\\n\\u0000]+) from ([^ ]+) port ([0-9]+) ssh2");
  private OpenSsh() {}

  public static JsonNode adapt(Boundary.Input input) {
    check(input.context().at("/parser/id").asString().equals("openssh-password"), "parser_binding");
    Boundary.validateContext(input.raw(), input.context());
    check(Json.sha(input.bytes()).equals(input.raw().at("/evidence/sha256").asString()), "record_digest");
    JsonNode result;
    try { result = parse(input); }
    catch (Unsupported e) { result = Boundary.diagnostic(input, "unsupported_source"); }
    catch (IllegalArgumentException e) { result = Boundary.diagnostic(input, "extraction_failed"); }
    if (result.path("kind").asString().equals("preservation"))
      Boundary.schema("urn:detectbridge:linux:1.0.0:preservation", result);
    return result;
  }

  private static JsonNode parse(Boundary.Input input) {
    String text = Boundary.text(input.bytes());
    if (text.endsWith("\n")) text = text.substring(0, text.length() - 1);
    check(!text.contains("\n") && !text.contains("\r") && !text.contains("\u0000"), "invalid_framing");
    if (!text.startsWith("<")) throw new Unsupported();
    Matcher h = HEADER.matcher(text); check(h.matches(), "invalid_rfc5424");
    check(Integer.parseInt(h.group(1)) <= 191
        && (h.group(1).equals("0") || !h.group(1).startsWith("0")), "invalid_priority");
    if (!Set.of("sshd", "sshd-session").contains(h.group(4))) throw new Unsupported();
    String rest = h.group(7); int end = structuredData(rest);
    check(end < rest.length() && rest.charAt(end) == ' ', "missing_message");
    String msg = rest.substring(end + 1);
    if (msg.startsWith("\ufeff")) msg = msg.substring(1);
    Matcher b = BODY.matcher(msg); if (!b.matches()) throw new Unsupported();
    check(b.group(2).codePointCount(0, b.group(2).length()) <= 100, "user_limit");
    String ip = b.group(3); check(ip(ip), "invalid_address");
    int port = Audit.number(b.group(4)); check(port >= 1 && port <= 65535, "invalid_port");
    String stamp = h.group(2), utc = null;
    if (!stamp.equals("-")) {
      check(stamp.matches("[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})"), "invalid_time");
      try {
        var time = OffsetDateTime.parse(stamp);
        check(time.getYear() >= 1 && time.getYear() <= 9999, "invalid_time");
        utc = time.toInstant().toString(); check(utc.matches("[0-9]{4}-.*"), "invalid_time");
      } catch (RuntimeException e) { throw new IllegalArgumentException("invalid_time"); }
    }
    if (!input.context().has("host_binding")) return Boundary.diagnostic(input, "identity_missing");
    JsonNode fields = Json.MAPPER.valueToTree(Map.of("user", b.group(2), "remote_address", ip,
        "rfc5424", Map.of("priority", h.group(1), "timestamp", stamp, "hostname", h.group(3),
            "app_name", h.group(4), "procid", h.group(5), "msgid", h.group(6),
            "structured_data", rest.substring(0, end))));
    ObjectNode event = Boundary.event(input.context(), List.of(input.raw()), utc,
        utc == null ? "missing" : "valid", stamp.equals("-") ? null : stamp, "not_required",
        true, List.of(), fields, Map.of("user", Map.of("name", b.group(2)),
            "source", Map.of("ip", ip, "port", port)));
    ((ObjectNode) event.get("event")).put("outcome", b.group(1).equals("Accepted") ? "success" : "failure");
    if (Json.bytes(event).length > Json.MAX_VALUE) return Boundary.diagnostic(input, "output_limit");
    return event;
  }

  static boolean ip(String value) {
    if (value.contains(":")) {
      if (!value.matches("[0-9a-fA-F:.]+")) return false;
      try { InetAddress.getByName(value); return true; }
      catch (Exception e) { return false; }
    }
    String[] parts = value.split("\\.", -1); if (parts.length != 4) return false;
    for (String p : parts) {
      if (!p.matches("0|[1-9][0-9]{0,2}") || Integer.parseInt(p) > 255) return false;
    }
    return true;
  }

  private static int name(String text, int pos) {
    int start = pos;
    while (pos < text.length()) {
      char c = text.charAt(pos);
      if (c < 33 || c > 126 || c == '=' || c == ']' || c == '"') break;
      pos++;
    }
    check(pos > start && pos - start <= 32, "invalid_sd_name"); return pos;
  }

  private static int structuredData(String text) {
    if (text.startsWith("-")) return 1;
    int pos = 0; Set<String> ids = new HashSet<>();
    while (pos < text.length() && text.charAt(pos) == '[') {
      int start = ++pos; pos = name(text, pos);
      check(ids.add(text.substring(start, pos)), "duplicate_sd_id");
      Set<String> params = new HashSet<>();
      while (pos < text.length() && text.charAt(pos) == ' ') {
        start = ++pos; pos = name(text, pos);
        check(params.add(text.substring(start, pos)), "duplicate_sd_param");
        check(text.startsWith("=\"", pos), "invalid_sd_param"); pos += 2;
        boolean closed = false;
        while (pos < text.length()) {
          char c = text.charAt(pos++);
          if (c == '"') { closed = true; break; }
          check(c != ']', "invalid_sd_escape");
          if (c == '\\') {
            check(pos < text.length() && "\\\"]".indexOf(text.charAt(pos++)) >= 0, "invalid_sd_escape");
          }
        }
        check(closed, "unterminated_sd_param");
      }
      check(pos < text.length() && text.charAt(pos++) == ']', "invalid_sd");
    }
    check(pos > 0, "invalid_sd"); return pos;
  }

  private static final class Unsupported extends RuntimeException {}
}
