package com.aiplatform.gateway.config;

import io.netty.channel.ChannelOption;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.netty.http.client.HttpClient;

import java.time.Duration;

@Configuration
public class WebClientConfig {

    @Value("${ai.service.url}")
    private String aiServiceUrl;

    @Value("${ai.service.connect-timeout-ms:3000}")
    private int connectTimeoutMs;

    @Value("${ai.service.response-timeout-s:60}")
    private int responseTimeoutS;

    @Bean
    public WebClient aiServiceClient(WebClient.Builder builder) {
        HttpClient httpClient = HttpClient.create()
            .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, connectTimeoutMs)
            // responseTimeout covers the entire response for blocking endpoints.
            // For long-lived SSE streams, 60 s is generous enough for slow Claude responses
            // while still bounding hung connections. ReadTimeoutHandler is intentionally
            // omitted — it would fire during Claude's silent reasoning phase and kill streams.
            .responseTimeout(Duration.ofSeconds(responseTimeoutS));

        return builder
            .baseUrl(aiServiceUrl)
            .clientConnector(new ReactorClientHttpConnector(httpClient))
            .codecs(config -> config.defaultCodecs().maxInMemorySize(10 * 1024 * 1024))
            .build();
    }
}
