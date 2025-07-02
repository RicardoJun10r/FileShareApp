package io.github.fileshare.model;

import java.time.LocalTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class Arquivo {

    private final DateTimeFormatter formatter = DateTimeFormatter.ofPattern("HH:mm:ss");

    private final ZoneId zoneId = ZoneId.of("America/Fortaleza");

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
        this.createdAt = LocalTime.now(this.zoneId);
        this.createdAt.format(this.formatter);
        this.expirationTime = createdAt.plusMinutes(5);
        this.expirationTime.format(this.formatter);
    }

}
