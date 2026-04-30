package com.aiplatform.gateway.config;

import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Duration;

@Configuration
public class CircuitBreakerConfig {

    /**
     * Circuit breaker protecting all calls to the downstream AI service.
     *
     * Thresholds (sliding-window of 5 calls):
     *   - Opens when ≥ 50% of calls fail
     *   - Stays open for 10 s before allowing half-open probes
     *   - Closes again after 3 consecutive successful probes
     */
    @Bean
    public CircuitBreaker aiServiceCircuitBreaker() {
        io.github.resilience4j.circuitbreaker.CircuitBreakerConfig config =
            io.github.resilience4j.circuitbreaker.CircuitBreakerConfig.custom()
                .slidingWindowType(io.github.resilience4j.circuitbreaker.CircuitBreakerConfig.SlidingWindowType.COUNT_BASED)
                .slidingWindowSize(5)
                .failureRateThreshold(50)
                .waitDurationInOpenState(Duration.ofSeconds(10))
                .permittedNumberOfCallsInHalfOpenState(3)
                .automaticTransitionFromOpenToHalfOpenEnabled(true)
                .build();

        return CircuitBreakerRegistry.of(config).circuitBreaker("aiService");
    }
}
