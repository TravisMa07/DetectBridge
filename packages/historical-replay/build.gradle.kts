plugins { java }
repositories { mavenCentral() }
dependencies {
    compileOnly(project(":linux-adapters"))
    compileOnly(project(":windows-adapters"))
    compileOnly(project(":detection-evaluator"))
    compileOnly(project(":transport-contracts"))
}
tasks.jar {
    archiveFileName.set("historical-replay.jar")
    isPreserveFileTimestamps = false
    isReproducibleFileOrder = true
    from(rootProject.file("LICENSE")) { into("META-INF"); rename { "DetectBridge-LICENSE" } }
}

dependencies { testImplementation(project(":integration-job")) }
val qualificationJar by tasks.registering(Jar::class) {
    dependsOn(tasks.testClasses)
    archiveFileName.set("historical-probe.jar")
    from(sourceSets.test.get().output)
    isPreserveFileTimestamps = false
    isReproducibleFileOrder = true
}
configurations.testImplementation { extendsFrom(configurations.compileOnly.get()) }
// The executor identity also binds its controlling CLI, validator and frozen wrappers.
tasks.jar {
    from(rootProject.file("tools")) {
        include("historical.py", "check_contracts.py")
        into("META-INF/historical/tools")
    }
    from(rootProject.file("uv.lock")) { into("META-INF/historical") }
    from(rootProject.file("contracts/historical-replay/v1")) {
        include("*.schema.json")
        into("META-INF/historical/schemas")
    }
}
