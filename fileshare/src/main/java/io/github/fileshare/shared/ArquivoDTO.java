package io.github.fileshare.shared;

import java.time.LocalTime;

import io.github.fileshare.model.Arquivo;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class ArquivoDTO {

    private Long id;

    private String name;

    private String type;

    private LocalTime createdAt;

    private LocalTime expirationTime;

    public ArquivoDTO toDTO(Arquivo arquivo) {
        this.id = arquivo.getId();
        this.name = arquivo.getName();
        this.type = arquivo.getType();
        this.createdAt = arquivo.getCreatedAt();
        this.expirationTime = arquivo.getExpirationTime();
        return new ArquivoDTO(id, name, type, createdAt, expirationTime);
    }

}
