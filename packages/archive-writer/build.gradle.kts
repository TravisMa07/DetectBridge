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
application { mainClass.set("io.detectbridge.archive.Main") }
tasks.shadowJar {
    archiveFileName.set("archive-writer.jar")
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

tasks.test { useJUnitPlatform(); systemProperty("repository.root", rootProject.projectDir) }
sourceSets.main { resources { srcDir(rootProject.file("contracts")); include("archive/v1/*.schema.json") } }
tasks.shadowJar { from(rootProject.file("LICENSE")) { into("META-INF"); rename { "DetectBridge-LICENSE" } } }

val qualificationJar by tasks.registering(Jar::class) {
    dependsOn(tasks.testClasses)
    archiveFileName.set("archive-probe.jar")
    from(sourceSets.test.get().output)
    isPreserveFileTimestamps = false
    isReproducibleFileOrder = true
}

tasks.test { inputs.dir(rootProject.file("contracts/archive/v1/fixtures")) }
tasks.shadowJar {
    from(rootProject.file("contracts/v1/NOTICE")) { into("META-INF"); rename { "ECS-NOTICE" } }
}
