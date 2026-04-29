package com.aiplatform.gateway.controller;

import io.github.resilience4j.circuitbreaker.CallNotPermittedException;
import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.reactor.circuitbreaker.operator.CircuitBreakerOperator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.core.io.buffer.DataBufferUtils;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientRequestException;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;
import reactor.core.scheduler.Schedulers;

import java.nio.charset.StandardCharsets;
import java.util.Map;

@RestController
public class ChatController {

    private static final Logger log = LoggerFactory.getLogger(ChatController.class);

    private static final String SERVICE_UNAVAILABLE_JSON =
        "{\"detail\":\"AI service is currently unavailable. Please try again shortly.\"}";
    private static final String SSE_UNAVAILABLE =
        "data: {\"error\":{\"code\":\"service_unavailable\",\"message\":\"AI service is currently unavailable. Please try again shortly.\"}}\n\ndata: [DONE]\n\n";

    private final WebClient webClient;
    private final CircuitBreaker circuitBreaker;

    public ChatController(WebClient aiServiceClient, CircuitBreaker aiServiceCircuitBreaker) {
        this.webClient = aiServiceClient;
        this.circuitBreaker = aiServiceCircuitBreaker;
    }

    @PostMapping(value = "/chat", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> chat(@RequestBody Map<String, Object> request) {
        try {
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
                .transformDeferred(CircuitBreakerOperator.of(circuitBreaker))
                .block();
        } catch (CallNotPermittedException e) {
            log.warn("Circuit breaker OPEN — rejecting /chat request");
            return ResponseEntity.status(503)
                .contentType(MediaType.APPLICATION_JSON)
                .body(SERVICE_UNAVAILABLE_JSON);
        } catch (WebClientRequestException e) {
            log.error("AI service connection error on /chat: {}", e.getMessage());
            return ResponseEntity.status(503)
                .contentType(MediaType.APPLICATION_JSON)
                .body(SERVICE_UNAVAILABLE_JSON);
        }
    }

    /**
     * Transparent SSE streaming proxy: raw bytes from the Python AI service are forwarded
     * verbatim so the frontend sees the exact same "data: {...}\n\n" wire format.
     * If the circuit breaker is open or the service is unreachable, a terminal SSE error
     * event is written so the frontend reaches a known [DONE] state.
     */
    @PostMapping("/chat/stream")
    public ResponseEntity<StreamingResponseBody> streamChat(@RequestBody Map<String, Object> request) {
        StreamingResponseBody body = outputStream -> {
            try {
                webClient.post()
                    .uri("/chat/stream")
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(request)
                    .retrieve()
                    .bodyToFlux(DataBuffer.class)
                    .transformDeferred(CircuitBreakerOperator.of(circuitBreaker))
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
            } catch (CallNotPermittedException e) {
                log.warn("Circuit breaker OPEN mid-stream — writing SSE error event");
                outputStream.write(SSE_UNAVAILABLE.getBytes(StandardCharsets.UTF_8));
                outputStream.flush();
            } catch (WebClientRequestException e) {
                log.error("AI service connection error on /chat/stream: {}", e.getMessage());
                outputStream.write(SSE_UNAVAILABLE.getBytes(StandardCharsets.UTF_8));
                outputStream.flush();
            }
        };

        return ResponseEntity.ok()
            .contentType(MediaType.TEXT_EVENT_STREAM)
            .body(body);
    }
}
