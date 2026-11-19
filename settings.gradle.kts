// Keep the verified marker on the Portal; resolve its libraries directly from Central.
pluginManagement {
    repositories {
        mavenCentral {
            content { excludeModule("com.gradleup.shadow", "com.gradleup.shadow.gradle.plugin") }
        }
        gradlePluginPortal {
            content { includeModule("com.gradleup.shadow", "com.gradleup.shadow.gradle.plugin") }
        }
    }
}

rootProject.name = "detectbridge"
include("transport-contracts", "transport-publisher", "transport-job")
project(":transport-contracts").projectDir = file("packages/transport-contracts")
project(":transport-publisher").projectDir = file("packages/transport-publisher")
project(":transport-job").projectDir = file("packages/transport-job")
include("detection-evaluator", "detection-job")
project(":detection-evaluator").projectDir = file("packages/detection-evaluator")
project(":detection-job").projectDir = file("packages/detection-job")
include("transport-writer")
project(":transport-writer").projectDir = file("packages/transport-writer")
include("windows-adapters")
project(":windows-adapters").projectDir = file("packages/windows-adapters")
include("linux-adapters")
project(":linux-adapters").projectDir = file("packages/linux-adapters")
include("linux-assembly-job")
project(":linux-assembly-job").projectDir = file("packages/linux-assembly-job")

include("integration-job")
project(":integration-job").projectDir = file("packages/integration-job")

include("integration-writer")
project(":integration-writer").projectDir = file("packages/integration-writer")

include("archive-writer")
project(":archive-writer").projectDir = file("packages/archive-writer")

include("historical-replay")
project(":historical-replay").projectDir = file("packages/historical-replay")

include("current-replay")
project(":current-replay").projectDir = file("packages/current-replay")

include("archive-maintenance")
project(":archive-maintenance").projectDir = file("packages/archive-maintenance")
