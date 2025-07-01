package io.github.fileshare.model;

import java.time.LocalTime;

import jakarta.persistence.PrePersist;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class Arquivo {

    private Long id;

    private String name;

    private String type;

    private byte[] content;

    private LocalTime createdAt;

    private LocalTime expirationTime;

    public Arquivo(String name, String type, byte[] content) {
        this.name = name;
        this.type = type;
        this.content = content;
    }

    @PrePersist
    void onCreate() {
        this.createdAt = LocalTime.now();
        this.expirationTime = createdAt.plusMinutes(5);
    }

}
