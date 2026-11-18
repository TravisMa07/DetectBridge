package io.detectbridge.history;
import java.nio.file.*;
/** Qualification-only reason visibility for original synthetic fixtures. */
public final class EngineProbe {
  public static void main(String[] args)throws Exception {
    if(!Bootstrap.sha(Path.of(args[0])).equals(Bootstrap.PRODUCER))throw new IllegalArgumentException("wrong_fixture_producer");
    Engine.execute(Path.of(args[1]),Path.of(args[2]));
  }
}
