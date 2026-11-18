package io.detectbridge.currentreplay;

import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;

/** Verify the supported producer before loading any of its classes. */
public final class Bootstrap {
  static final String PRODUCER="51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d";
  static void safe(Path path)throws IOException {
    for(Path p=path.toAbsolutePath();p!=null;p=p.getParent())if(Files.isSymbolicLink(p))throw new IOException("current_unsafe_path");
  }
  static byte[] read(Path path,int cap)throws Exception {
    safe(path);if(!Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS)||Files.size(path)>cap)throw new IOException("current_file_limit");
    try(var in=Files.newInputStream(path,LinkOption.NOFOLLOW_LINKS)){byte[] value=in.readNBytes(cap+1);if(value.length>cap)throw new IOException("current_file_limit");return value;}
  }
  static String sha(byte[] value)throws Exception {return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value));}
  public static void main(String[] args) {
    try {
      if(args.length!=3)throw new IOException("current_arguments");
      Path producer=Path.of(args[0]);safe(producer);producer=producer.toRealPath(LinkOption.NOFOLLOW_LINKS);
      if(!sha(read(producer,32*1048576)).equals(PRODUCER))throw new IOException("current_unsupported_producer");
      for(String name:List.of("io.detectbridge.integration.Machine","io.detectbridge.integration.LocalEvidence","io.detectbridge.integration.Schemas","io.detectbridge.linux.Assembler","io.detectbridge.linux.Boundary","io.detectbridge.windows.WindowsAdapter","io.detectbridge.detection.Evaluator","io.detectbridge.detection.IntegrationOutputs","io.detectbridge.transport.Json","tools.jackson.databind.JsonNode","com.networknt.schema.SchemaRegistry")) {
        Class<?> type=Class.forName(name,false,Bootstrap.class.getClassLoader());
        if(!Path.of(type.getProtectionDomain().getCodeSource().getLocation().toURI()).toRealPath().equals(producer))throw new IOException("current_class_origin");
      }
      Engine.execute(Path.of(args[1]),Path.of(args[2]));
    }catch(Throwable failure) {
      if(args.length==3)try {
        Path file=Path.of(args[2]).getParent().resolve("failure.txt");safe(file);
        try(var out=Files.newOutputStream(file,StandardOpenOption.CREATE_NEW);var limited=new FilterOutputStream(out) {
          int remaining=1048576;
          public void write(int b)throws IOException{if(remaining>0){out.write(b);remaining--;}}
          public void write(byte[] b,int off,int len)throws IOException{int count=Math.min(remaining,len);if(count>0){out.write(b,off,count);remaining-=count;}}
        };var print=new PrintWriter(new OutputStreamWriter(limited,java.nio.charset.StandardCharsets.UTF_8))) {failure.printStackTrace(print);}
      }catch(Exception ignored){}
      System.err.println("current_execution_failed:"+failure.getClass().getSimpleName());System.exit(1);
    }
  }
}
