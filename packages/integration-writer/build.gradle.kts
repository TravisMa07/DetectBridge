plugins {
    application
    alias(libs.plugins.shadow)
}
repositories { mavenCentral() }
dependencies {
    implementation(project(":transport-contracts"))
    implementation(project(":detection-evaluator"))
    testImplementation(project(":integration-job"))
    testImplementation(project(":linux-adapters"))
    implementation(libs.validator)
    runtimeOnly(libs.slf4j.nop)
    testImplementation(platform(libs.junit.bom))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}
application { mainClass.set("io.detectbridge.search.Main") }
tasks.shadowJar {
    archiveFileName.set("search-writer.jar")
    duplicatesStrategy = DuplicatesStrategy.INCLUDE
    filesMatching("v1/**") { duplicatesStrategy = DuplicatesStrategy.EXCLUDE }
    mergeServiceFiles()
    for (notice in listOf("LICENSE", "NOTICE", "LICENSE.txt", "NOTICE.txt", "DEPENDENCIES",
            "FastDoubleParser-LICENSE", "FastDoubleParser-ThirdParty-LICENSE", "Schubfach-LICENSE")) {
        append("META-INF/$notice")
    }
    isPreserveFileTimestamps = false
    isReproducibleFileOrder = true
    exclude("META-INF/*.SF", "META-INF/*.RSA", "META-INF/*.DSA", "module-info.class", "META-INF/versions/**/module-info.class")
}

tasks.test { useJUnitPlatform(); dependsOn(":integration-job:prepareIntegrationCases"); systemProperty("repository.root", rootProject.projectDir) }
sourceSets.main { resources { srcDir(rootProject.file("contracts")); include("search-writer/v1/*.schema.json") } }
sourceSets.test { resources.srcDir(rootProject.file("contracts")) }

tasks.shadowJar {
    from(rootProject.file("LICENSE")) { into("META-INF"); rename { "DetectBridge-LICENSE" } }
    from(rootProject.file("contracts/v1/NOTICE")) { into("META-INF"); rename { "ECS-NOTICE" } }
}
