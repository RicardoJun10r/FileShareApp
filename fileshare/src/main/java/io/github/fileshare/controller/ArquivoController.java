package io.github.fileshare.controller;

import java.util.List;
import java.util.stream.Collectors;

import org.springframework.core.io.ByteArrayResource;
import org.springframework.core.io.Resource;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import io.github.fileshare.model.Arquivo;
import io.github.fileshare.service.ArquivoService;
import io.github.fileshare.shared.ArquivoDTO;
import lombok.RequiredArgsConstructor;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class ArquivoController {

    private final ArquivoService arquivoService;

    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<String> upload(@RequestParam("file") MultipartFile file) {
        this.arquivoService.upload(file);
        return ResponseEntity.ok("Arquivo salvo com sucesso");
    }

    @GetMapping(value = "/download", produces = MediaType.APPLICATION_OCTET_STREAM_VALUE)
    public ResponseEntity<Resource> download(@RequestParam Long id) {
        Arquivo arquivo = this.arquivoService.download(id);
        ByteArrayResource resource = new ByteArrayResource(arquivo.getContent());

        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(arquivo.getType()))
                .header(org.springframework.http.HttpHeaders.CONTENT_DISPOSITION,
                        "attachment; filename=\"" + arquivo.getName() + "\"")
                .body(resource);
    }

    @GetMapping
    public ResponseEntity<List<ArquivoDTO>> list() {
        return ResponseEntity.ok(this.arquivoService.list().stream().map(arq -> {
            ArquivoDTO dto = new ArquivoDTO();
            return dto.toDTO(arq);
        }).collect(Collectors.toList()));
    }

}
