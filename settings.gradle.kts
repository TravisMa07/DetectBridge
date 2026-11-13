rootProject.name = "detectbridge"
include("transport-contracts", "transport-publisher", "transport-job")
project(":transport-contracts").projectDir = file("packages/transport-contracts")
project(":transport-publisher").projectDir = file("packages/transport-publisher")
project(":transport-job").projectDir = file("packages/transport-job")
