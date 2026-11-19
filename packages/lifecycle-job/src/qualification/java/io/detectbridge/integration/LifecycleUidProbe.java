package io.detectbridge.integration;

import static io.detectbridge.integration.LifecycleSupport.*;
import java.nio.file.*;
import java.util.Map;
import java.util.Set;

/** Read-only native UID regression; also runs against historical privatePath implementations. */
public final class LifecycleUidProbe {
  public static void main(String[] args)throws Exception {
    if(args.length!=1)throw new IllegalArgumentException("lifecycle_arguments");
    long nativeUid=new com.sun.security.auth.module.UnixSystem().getUid();
    long kernelUid=((Number)Files.getAttribute(Path.of("/proc/self"),"unix:uid")).longValue();
    long pathUid=((Number)Files.getAttribute(Path.of(args[0]),"unix:uid",LinkOption.NOFOLLOW_LINKS)).longValue();
    String category="ok";boolean valid=true;
    try{privatePath(Path.of(args[0]),true);}catch(IllegalArgumentException failure){valid=false;category=Set.of("lifecycle_private_owner","lifecycle_private_path","lifecycle_private_mode","lifecycle_symlink").contains(failure.getMessage())?failure.getMessage():"unclassified";}
    System.out.println(new String(bytes(value(Map.of("version","1.0.0","unixsystem_uid",nativeUid,"kernel_uid",kernelUid,"path_uid",pathUid,"private_path_valid",valid,"category",category))),java.nio.charset.StandardCharsets.UTF_8));
    if(!valid)System.exit(1);
  }
}
