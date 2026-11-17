FROM flink:2.2.1-scala_2.12-java17@sha256:55ccb2ad4b98362c3f3503c5a6d7cd00b92eb25e38815ddaf0be5903ade54ffe
USER 9999:9999
COPY --chown=9999:9999 search-writer.jar /opt/detectbridge/search-writer.jar
ENTRYPOINT ["java", "-Xmx256m", "-cp", "/opt/detectbridge/search-writer.jar", "io.detectbridge.search.Main"]
CMD ["serve", "/secrets"]
