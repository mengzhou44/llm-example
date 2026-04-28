package com.aiplatform.gateway.controller;

import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.util.Map;

@RestController
public class KnowledgeController {

    private final WebClient webClient;

    public KnowledgeController(WebClient aiServiceClient) {
        this.webClient = aiServiceClient;
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
        return spec.exchangeToMono(response ->
            response.bodyToMono(String.class)
                .defaultIfEmpty("")
                .map(body -> ResponseEntity
                    .status(response.statusCode())
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body))
        ).block();
    }
}
