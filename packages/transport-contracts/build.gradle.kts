plugins { `java-library` }
repositories { mavenCentral() }
dependencies {
    api(libs.jackson)
    api("org.apache.kafka:kafka-clients:4.2.0")
    implementation(libs.validator)
    testImplementation(platform(libs.junit.bom))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}
tasks.test { useJUnitPlatform() }
sourceSets.main { resources.srcDir(rootProject.file("contracts")) }
sourceSets.test { resources.srcDir(rootProject.file("contracts")) }
