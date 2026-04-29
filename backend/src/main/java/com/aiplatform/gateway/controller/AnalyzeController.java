package com.aiplatform.gateway.controller;

import io.github.resilience4j.circuitbreaker.CallNotPermittedException;
import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.reactor.circuitbreaker.operator.CircuitBreakerOperator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientRequestException;

import java.util.Map;

@RestController
public class AnalyzeController {

    private static final Logger log = LoggerFactory.getLogger(AnalyzeController.class);

    private static final String SERVICE_UNAVAILABLE_JSON =
        "{\"detail\":\"AI service is currently unavailable. Please try again shortly.\"}";

    private final WebClient webClient;
    private final CircuitBreaker circuitBreaker;

    public AnalyzeController(WebClient aiServiceClient, CircuitBreaker aiServiceCircuitBreaker) {
        this.webClient = aiServiceClient;
        this.circuitBreaker = aiServiceCircuitBreaker;
    }

    @PostMapping(value = "/analyze/issue", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> analyzeIssue(@RequestBody Map<String, Object> request) {
        try {
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
                )
                .transformDeferred(CircuitBreakerOperator.of(circuitBreaker))
                .block();
        } catch (CallNotPermittedException e) {
            log.warn("Circuit breaker OPEN — rejecting /analyze/issue request");
            return ResponseEntity.status(503)
                .contentType(MediaType.APPLICATION_JSON)
                .body(SERVICE_UNAVAILABLE_JSON);
        } catch (WebClientRequestException e) {
            log.error("AI service connection error on /analyze/issue: {}", e.getMessage());
            return ResponseEntity.status(503)
                .contentType(MediaType.APPLICATION_JSON)
                .body(SERVICE_UNAVAILABLE_JSON);
        }
    }
}
