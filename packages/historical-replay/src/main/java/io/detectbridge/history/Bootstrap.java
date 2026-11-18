package io.detectbridge.history;

import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;

/** JDK-only trust boundary: reject a substituted producer before loading its classes. */
public final class Bootstrap {
  public static final String PRODUCER = "51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d";
  public static void safe(Path path) throws IOException {
    for(Path p=path.toAbsolutePath();p!=null;p=p.getParent())
      if(Files.isSymbolicLink(p))throw new IOException("historical_unsafe_path");
  }
  public static String sha(Path path) throws Exception {
    safe(path);if(!Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS)||Files.size(path)>32L*1048576)throw new IOException("historical_artifact_limit");
    var digest=MessageDigest.getInstance("SHA-256");
    try(var in=Files.newInputStream(path,LinkOption.NOFOLLOW_LINKS)){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1)digest.update(b,0,n);}
    return HexFormat.of().formatHex(digest.digest());
  }
  public static void main(String[] args) {
    try {
      if(args.length!=3)throw new IOException("historical_arguments");
      safe(Path.of(args[0]));Path producer=Path.of(args[0]).toRealPath(LinkOption.NOFOLLOW_LINKS);
      if(!sha(producer).equals(PRODUCER))throw new IOException("historical_unsupported_producer");
      for(String name:List.of("io.detectbridge.integration.LocalEvidence","io.detectbridge.integration.Schemas","io.detectbridge.linux.Assembler","io.detectbridge.linux.Audit","io.detectbridge.linux.Boundary","io.detectbridge.linux.OpenSsh","tools.jackson.databind.JsonNode","com.networknt.schema.SchemaRegistry","io.detectbridge.windows.WindowsAdapter","io.detectbridge.detection.Evaluator","io.detectbridge.detection.IntegrationOutputs","io.detectbridge.transport.Json")) {
        Class<?> type=Class.forName(name,false,Bootstrap.class.getClassLoader());
        Path actual=Path.of(type.getProtectionDomain().getCodeSource().getLocation().toURI()).toRealPath();
        if(!actual.equals(producer))throw new IOException("historical_class_origin");
      }
      Engine.execute(Path.of(args[1]),Path.of(args[2]));
    } catch(Throwable failure) {
      // Never print imported source bodies, parser messages or arbitrary paths.
      Throwable cause=failure;while(cause instanceof java.lang.reflect.InvocationTargetException && cause.getCause()!=null)cause=cause.getCause();
      String reason=cause.getMessage();
      if(reason==null||!reason.matches("[a-z_]{1,80}"))reason="historical_execution_failed";
      System.err.println(reason+":"+cause.getClass().getSimpleName());
      System.exit(1);
    }
  }
}
