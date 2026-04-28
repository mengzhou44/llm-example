package com.aiplatform.gateway.controller;

import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.core.io.buffer.DataBufferUtils;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;
import reactor.core.scheduler.Schedulers;

import java.util.Map;

@RestController
public class ChatController {

    private final WebClient webClient;

    public ChatController(WebClient aiServiceClient) {
        this.webClient = aiServiceClient;
    }

    @PostMapping(value = "/chat", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> chat(@RequestBody Map<String, Object> request) {
        return webClient.post()
            .uri("/chat")
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
            .block();
    }

    /**
     * Transparent SSE streaming proxy: raw bytes from the Python AI service are forwarded
     * verbatim so the frontend sees the exact same "data: {...}\n\n" wire format.
     */
    @PostMapping("/chat/stream")
    public ResponseEntity<StreamingResponseBody> streamChat(@RequestBody Map<String, Object> request) {
        StreamingResponseBody body = outputStream -> webClient.post()
            .uri("/chat/stream")
            .contentType(MediaType.APPLICATION_JSON)
            .bodyValue(request)
            .retrieve()
            .bodyToFlux(DataBuffer.class)
            // Move off the Netty I/O thread before doing blocking OutputStream writes.
            .publishOn(Schedulers.boundedElastic())
            .doOnNext(buffer -> {
                try {
                    byte[] bytes = new byte[buffer.readableByteCount()];
                    buffer.read(bytes);
                    outputStream.write(bytes);
                    outputStream.flush();
                } catch (Exception e) {
                    throw new RuntimeException(e);
                } finally {
                    DataBufferUtils.release(buffer);
                }
            })
            .blockLast();

        return ResponseEntity.ok()
            .contentType(MediaType.TEXT_EVENT_STREAM)
            .body(body);
    }
}
