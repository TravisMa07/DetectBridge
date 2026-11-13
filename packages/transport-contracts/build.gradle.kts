plugins { `java-library` }
repositories { mavenCentral() }
dependencies {
    api(libs.jackson)
    api(libs.kafka.clients)
    implementation(libs.validator)
    testImplementation(platform(libs.junit.bom))
    testImplementation(libs.codec.lz4)
    testImplementation(libs.codec.snappy)
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}
tasks.test { useJUnitPlatform() }
sourceSets.main { resources { srcDir(rootProject.file("contracts")); include("v1/*.schema.json", "replay/v1/*.schema.json", "transport/v1/*.schema.json") } }
sourceSets.test { resources.srcDir(rootProject.file("contracts")) }
