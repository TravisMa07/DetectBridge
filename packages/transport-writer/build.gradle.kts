plugins {
    application
    alias(libs.plugins.shadow)
}
repositories { mavenCentral() }
dependencies {
    implementation(project(":transport-contracts"))
    implementation(libs.validator)
    runtimeOnly(libs.slf4j.nop)
    testImplementation(platform(libs.junit.bom))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}
application { mainClass.set("io.detectbridge.writer.Main") }
tasks.shadowJar {
    archiveFileName.set("writer.jar")
    duplicatesStrategy = DuplicatesStrategy.INCLUDE
    mergeServiceFiles()
    for (notice in listOf("LICENSE", "NOTICE", "LICENSE.txt", "NOTICE.txt", "DEPENDENCIES",
            "FastDoubleParser-LICENSE", "FastDoubleParser-ThirdParty-LICENSE", "Schubfach-LICENSE")) {
        append("META-INF/$notice")
    }
    isPreserveFileTimestamps = false
    isReproducibleFileOrder = true
    exclude("META-INF/*.SF", "META-INF/*.RSA", "META-INF/*.DSA", "module-info.class", "META-INF/versions/**/module-info.class")
}

tasks.test { useJUnitPlatform() }
sourceSets.main { resources { srcDir(rootProject.file("contracts")); include("writer/v1/*.schema.json") } }
sourceSets.test { resources.srcDir(rootProject.file("contracts")) }
