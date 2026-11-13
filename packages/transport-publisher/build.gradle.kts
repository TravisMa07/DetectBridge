plugins { application; alias(libs.plugins.shadow) }
repositories { mavenCentral() }
dependencies {
    implementation(project(":transport-contracts"))
    runtimeOnly("org.slf4j:slf4j-nop:2.0.20")
}
application { mainClass.set("io.detectbridge.transport.Publisher") }
tasks.shadowJar { archiveFileName.set("publisher.jar"); duplicatesStrategy = DuplicatesStrategy.INCLUDE; mergeServiceFiles(); append("META-INF/LICENSE"); append("META-INF/NOTICE"); append("META-INF/DEPENDENCIES"); append("META-INF/FastDoubleParser-LICENSE"); isPreserveFileTimestamps = false; isReproducibleFileOrder = true; exclude("META-INF/*.SF", "META-INF/*.RSA", "META-INF/*.DSA") }
