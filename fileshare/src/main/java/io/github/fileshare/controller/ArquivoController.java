package io.github.fileshare.controller;

import java.util.List;

import org.springframework.core.io.Resource;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import io.github.fileshare.model.Arquivo;
import io.github.fileshare.service.ArquivoService;
import lombok.RequiredArgsConstructor;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class ArquivoController {

    private final ArquivoService arquivoService;

    @PostMapping("/upload")
    public ResponseEntity<String> upload(@RequestBody MultipartFile file) {
        this.arquivoService.upload(file);
        return ResponseEntity.ok("Arquivo salvo com sucesso");
    }

    @GetMapping("/download")
    public ResponseEntity<Resource> download(@RequestParam Long id) {
        return ResponseEntity.ok(this.arquivoService.download(id));
    }

    @GetMapping
    public ResponseEntity<List<Arquivo>> list() {
        return ResponseEntity.ok(this.arquivoService.list());
    }

}
