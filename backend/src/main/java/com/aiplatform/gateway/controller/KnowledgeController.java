package com.aiplatform.gateway.controller;

import io.github.resilience4j.circuitbreaker.CallNotPermittedException;
import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.reactor.circuitbreaker.operator.CircuitBreakerOperator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientRequestException;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.util.Map;

@RestController
public class KnowledgeController {

    private static final Logger log = LoggerFactory.getLogger(KnowledgeController.class);

    private static final String SERVICE_UNAVAILABLE_JSON =
        "{\"detail\":\"AI service is currently unavailable. Please try again shortly.\"}";

    private final WebClient webClient;
    private final CircuitBreaker circuitBreaker;

    public KnowledgeController(WebClient aiServiceClient, CircuitBreaker aiServiceCircuitBreaker) {
        this.webClient = aiServiceClient;
        this.circuitBreaker = aiServiceCircuitBreaker;
    }

    @GetMapping(value = "/knowledge/documents", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> listDocuments() {
        return proxy(webClient.get().uri("/knowledge/documents"));
    }

    @DeleteMapping(value = "/knowledge/documents/{docId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> deleteDocument(@PathVariable String docId) {
        return proxy(webClient.delete().uri("/knowledge/documents/{id}", docId));
    }

    @PostMapping(value = "/knowledge/search", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> search(@RequestBody Map<String, Object> request) {
        return proxy(webClient.post()
            .uri("/knowledge/search")
            .contentType(MediaType.APPLICATION_JSON)
            .bodyValue(request));
    }

    @PostMapping(value = "/knowledge/upload",
                 consumes = MediaType.MULTIPART_FORM_DATA_VALUE,
                 produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> uploadDocument(@RequestParam("file") MultipartFile file) {
        try {
            final String filename = file.getOriginalFilename() != null
                ? file.getOriginalFilename() : "upload";
            final String contentType = file.getContentType() != null
                ? file.getContentType() : "application/octet-stream";

            MultipartBodyBuilder builder = new MultipartBodyBuilder();
            builder.part("file", new ByteArrayResource(file.getBytes()) {
                @Override public String getFilename() { return filename; }
            }).contentType(MediaType.parseMediaType(contentType));

            return proxy(webClient.post()
                .uri("/knowledge/upload")
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .bodyValue(builder.build()));
        } catch (IOException e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Failed to read uploaded file");
        }
    }

    private ResponseEntity<String> proxy(WebClient.RequestHeadersSpec<?> spec) {
        try {
            return spec.exchangeToMono(response ->
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
            log.warn("Circuit breaker OPEN — rejecting knowledge request");
            return ResponseEntity.status(503)
                .contentType(MediaType.APPLICATION_JSON)
                .body(SERVICE_UNAVAILABLE_JSON);
        } catch (WebClientRequestException e) {
            log.error("AI service connection error on knowledge endpoint: {}", e.getMessage());
            return ResponseEntity.status(503)
                .contentType(MediaType.APPLICATION_JSON)
                .body(SERVICE_UNAVAILABLE_JSON);
        }
    }
}
