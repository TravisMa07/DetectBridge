package io.detectbridge.windows;

import static io.detectbridge.detection.Contracts.check;

import io.detectbridge.transport.Json;
import java.io.IOException;
import java.net.URI;
import java.nio.file.*;
import java.util.*;
import tools.jackson.databind.JsonNode;

/** Explicitly supplied, retained evidence only. I/O is retryable and is never a nonmatch. */
@FunctionalInterface
public interface EvidenceResolver {
  byte[] resolve(JsonNode raw) throws IOException;

  final class IntegrityFailure extends IllegalArgumentException {
    public IntegrityFailure() { super("evidence_integrity"); }
  }

  /** Registered content-addressed objects; URI values never select filesystem paths. */
  static EvidenceResolver local(Path objects) {
    return raw -> {
      try {
        var e = raw.get("evidence");
        byte[] record;
        if (e.has("inline")) {
          String value = e.get("inline").asString();
          if (e.get("encoding").asString().equals("utf-8")) record = value.getBytes(java.nio.charset.StandardCharsets.UTF_8);
          else {
            check(value.length() % 4 == 0 && value.matches("[A-Za-z0-9+/]*={0,2}"), "encoding");
            record = Base64.getDecoder().decode(value);
          }
        } else {
          var r = e.get("reference");
          String hash = r.get("object_sha256").asString();
          check(hash.matches("[a-f0-9]{64}"), "object_hash");
          URI uri = URI.create(r.get("uri").asString());
          check(Set.of("urn", "file", "https", "s3").contains(uri.getScheme()), "uri_scheme");
          check(uri.getRawUserInfo() == null && uri.getRawQuery() == null && uri.getRawFragment() == null
              && (uri.getRawAuthority() == null || !uri.getRawAuthority().contains("@")), "unsafe_uri");
          if (uri.getScheme().equals("urn")) check(uri.toString().equals("urn:sha256:" + hash), "content_address");
          if (Set.of("https", "s3").contains(uri.getScheme())) check(uri.getHost() != null, "uri_host");
          byte[] object;
          try (var in = Files.newInputStream(objects.resolve(hash))) { object = in.readNBytes(32 * 1024 * 1024 + 1); }
          check(object.length <= 32 * 1024 * 1024 && Json.sha(object).equals(hash), "object_integrity");
          long offset = 0, length = object.length;
          if (r.has("byte_range")) {
            var range = r.get("byte_range");
            check(range.get("offset").isIntegralNumber() && range.get("length").isIntegralNumber(), "range_integer");
            offset = range.get("offset").asLong(); length = range.get("length").asLong();
          }
          check(offset >= 0 && length > 0 && offset <= object.length && length <= object.length - offset, "range_bounds");
          check(offset == 0 || object[(int) offset - 1] == '\n', "record_start");
          long position = 0;
          for (int i = 0; i < offset; i++) if (object[i] == '\n') position++;
          if (raw.path("cursor").path("kind").asString().equals("dataset")) {
            check(raw.get("cursor").get("artifact_sha256").asString().equals(hash)
                && raw.get("cursor").get("position").asLong() == position, "cursor_range");
          }
          record = Arrays.copyOfRange(object, (int) offset, (int) (offset + length));
          check(offset + length == object.length || record[record.length - 1] == '\n', "record_end");
        }
        check(record.length <= Json.MAX_VALUE && Json.sha(record).equals(e.get("sha256").asString()), "record_digest");
        for (int i = 0; i < record.length - 1; i++) check(record[i] != '\n', "record_framing");
        return record;
      } catch (IllegalArgumentException ex) { throw new IntegrityFailure(); }
    };
  }
}
