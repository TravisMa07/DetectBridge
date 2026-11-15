package io.detectbridge.linux;

import static org.junit.jupiter.api.Assertions.*;
import static io.detectbridge.linux.Fixtures.*;

import java.util.*;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

class OpenSshTest {
  static String auth(String body) { return "<38>1 2026-01-01T00:00:00Z display sshd 7 - - " + body + "\n"; }
  static final String ACCEPT = "Accepted password for alice from 192.0.2.1 port 2222 ssh2";
  static JsonNode adapt(String text) throws Exception { return OpenSsh.adapt(input(text, 0, context(true))); }
  @Test void literalIpv4Ipv6OutcomeAndTimeFallback() throws Exception {
    JsonNode accepted = adapt(auth(ACCEPT));
    assertEquals("success", accepted.at("/event/outcome").asString());
    assertEquals("alice", accepted.at("/user/name").asString()); assertEquals(2222, accepted.at("/source/port").asInt());
    assertEquals("192.0.2.1", accepted.at("/source/ip").asString());
    assertEquals("host-a", accepted.at("/host/id").asString()); assertFalse(accepted.get("host").has("name"));
    JsonNode failed = adapt(auth(ACCEPT.replace("Accepted", "Failed").replace("192.0.2.1", "2001:db8::1")));
    assertEquals("failure", failed.at("/event/outcome").asString()); assertEquals("2001:db8::1", failed.at("/source/ip").asString());
    JsonNode fallback = adapt(auth(ACCEPT).replace("2026-01-01T00:00:00Z", "-"));
    assertEquals(FIRST, fallback.get("@timestamp").asString()); assertEquals("missing", fallback.at("/detectbridge/time/quality").asString());
    assertEquals("eligible", fallback.at("/detectbridge/quality/eligibility").asString());
    assertEquals("timestamp_missing", fallback.at("/detectbridge/quality/diagnostics/0/code").asString());
    JsonNode offset = adapt(auth(ACCEPT).replace("2026-01-01T00:00:00Z", "2026-01-01T01:00:00.123456+01:00"));
    assertEquals("2026-01-01T00:00:00.123456Z", offset.get("@timestamp").asString());
  }
  @Test void structuredDataAndSessionAppAreValidatedAndPreserved() throws Exception {
    String text = auth(ACCEPT).replace("sshd 7 - - ", "sshd-session 7 ID [capture@32473 name=\"a\\]b\"][x] ");
    JsonNode e = adapt(text); assertEquals("alice", e.at("/user/name").asString());
    assertEquals("[capture@32473 name=\"a\\]b\"][x]", e.at("/source_fields/rfc5424/structured_data").asString());
    assertEquals("alice", adapt(auth("\ufeff" + ACCEPT)).at("/user/name").asString());
    for (String sd : List.of("[x a=\"broken]", "[x a=\"bad\\q\"]", "[x][x]", "[x a=\"1\" a=\"2\"]", "[x a=\"bad]\"]"))
      assertEquals("extraction_failed", adapt(auth(ACCEPT).replace(" 7 - - ", " 7 - " + sd + " ")).get("code").asString(), sd);
  }
  @Test void malformedHeaderPortIpAndTimestampStayInvalid() throws Exception {
    for (String text : List.of(auth(ACCEPT).replace("<38>", "<192>"), auth(ACCEPT).replace("<38>", "<038>"),
        auth(ACCEPT).replace("port 2222", "port 0"), auth(ACCEPT).replace("port 2222", "port 65536"),
        auth(ACCEPT).replace("192.0.2.1", "localhost"), auth(ACCEPT).replace("192.0.2.1", "192.00.2.1"),
        auth(ACCEPT).replace("192.0.2.1", "2001:db8::1%eth0"), auth(ACCEPT).replace("192.0.2.1", "2001:::1"),
        auth(ACCEPT).replace("2026-01-01", "2026-02-30"), auth(ACCEPT).replace("00:00:00Z", "00:00:60Z"),
        auth(ACCEPT).replace("00:00:00Z", "00:00:00.1234567Z"), auth(ACCEPT).replace("<38>1 ", "<38>2 "),
        auth(ACCEPT) + auth(ACCEPT)))
      assertEquals("extraction_failed", adapt(text).get("code").asString(), text);
  }
  @Test void excludedGrammarDoesNotProduceAnAuthEvent() throws Exception {
    for (String text : List.of(auth(ACCEPT.replace("password", "publickey")), auth(ACCEPT.replace("for alice", "for invalid user alice")),
        auth("pam_unix(sshd:auth): authentication failure"), auth(ACCEPT.replace("Accepted", "Accepté")),
        auth(ACCEPT + ": extra"), "Jan  1 00:00:00 display sshd[7]: " + ACCEPT + "\n",
        "{\"MESSAGE\":\"" + ACCEPT + "\"}", auth(ACCEPT).replace("sshd 7", "other 7"))) {
      JsonNode result = adapt(text); assertEquals("unsupported_source", result.get("code").asString()); assertFalse(result.has("@timestamp"));
    }
    ObjectNode c = context(true); c.remove("host_binding");
    assertEquals("identity_missing", OpenSsh.adapt(input(auth(ACCEPT), 0, c)).get("code").asString());
  }
}
