plugins { application; alias(libs.plugins.shadow) }
repositories { mavenCentral() }
dependencies {
    implementation(project(":transport-contracts"))
    implementation(libs.flink.kafka)
    implementation("org.apache.flink:flink-connector-base:2.2.1")
    compileOnly(libs.flink.streaming)
    compileOnly(libs.flink.clients)
}
application { mainClass.set("io.detectbridge.transport.RelayJob") }
tasks.shadowJar { archiveFileName.set("transport-job.jar"); duplicatesStrategy = DuplicatesStrategy.INCLUDE; mergeServiceFiles(); append("META-INF/LICENSE"); append("META-INF/NOTICE"); append("META-INF/DEPENDENCIES"); append("META-INF/FastDoubleParser-LICENSE"); isPreserveFileTimestamps = false; isReproducibleFileOrder = true; exclude("META-INF/*.SF", "META-INF/*.RSA", "META-INF/*.DSA") }

configurations.runtimeClasspath { exclude(group = "org.slf4j") }
