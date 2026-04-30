#!/bin/bash
# Starts the Spring Boot gateway on port 4000.
# Requires Java 21 and Maven 3.x. First run downloads dependencies (~2 min).
cd "$(dirname "$0")"
mvn -q spring-boot:run
