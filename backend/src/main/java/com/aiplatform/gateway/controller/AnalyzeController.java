package com.aiplatform.gateway.controller;

import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.Map;

@RestController
public class AnalyzeController {

    private final WebClient webClient;

    public AnalyzeController(WebClient aiServiceClient) {
        this.webClient = aiServiceClient;
    }

    @PostMapping(value = "/analyze/issue", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> analyzeIssue(@RequestBody Map<String, Object> request) {
        return webClient.post()
            .uri("/analyze/issue")
            .contentType(MediaType.APPLICATION_JSON)
            .bodyValue(request)
            .exchangeToMono(response ->
                response.bodyToMono(String.class)
                    .defaultIfEmpty("")
                    .map(body -> ResponseEntity
                        .status(response.statusCode())
                        .contentType(MediaType.APPLICATION_JSON)
                        .body(body))
            ).block();
    }
}
