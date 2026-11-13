FROM flink:2.2.1-scala_2.12-java17@sha256:55ccb2ad4b98362c3f3503c5a6d7cd00b92eb25e38815ddaf0be5903ade54ffe
USER 9999:9999
COPY --chown=9999:9999 transport-job.jar /opt/detectbridge/transport-job.jar
COPY --chown=9999:9999 publisher.jar /opt/detectbridge/publisher.jar
COPY --chown=9999:9999 log4j-console.properties /opt/flink/conf/log4j-console.properties
