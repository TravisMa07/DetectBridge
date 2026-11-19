plugins { java }
repositories { mavenCentral() }
dependencies {
    compileOnly(project(":integration-job"))
    compileOnly(project(":linux-adapters"))
    compileOnly(project(":detection-evaluator"))
    compileOnly(project(":transport-contracts"))
}
tasks.jar {
    archiveFileName.set("current-replay.jar")
    isPreserveFileTimestamps = false
    isReproducibleFileOrder = true
    from(rootProject.file("LICENSE")) { into("META-INF"); rename { "DetectBridge-LICENSE" } }
    from(rootProject.file("tools")) {
        include("current_replay.py", "historical.py", "check_contracts.py")
        into("META-INF/current/tools")
    }
    from(rootProject.file("uv.lock")) { into("META-INF/current") }
    from(rootProject.file("contracts/current-replay/v1")) {
        include("*.schema.json"); into("META-INF/current/schemas")
    }
    from(rootProject.file("contracts/historical-replay/v1")) {
        include("*.schema.json"); into("META-INF/current/historical-schemas")
    }
}
