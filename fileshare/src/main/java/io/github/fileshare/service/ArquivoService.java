package io.github.fileshare.service;

import java.util.List;

import org.springframework.core.io.ByteArrayResource;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import io.github.fileshare.exception.ErroAoBaixar;
import io.github.fileshare.exception.ErroAoSalvar;
import io.github.fileshare.model.Arquivo;
import io.github.fileshare.repository.ArquivoRepository;
import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class ArquivoService {

    private final ArquivoRepository arquivoRepository;

    public void upload(MultipartFile file) {
        try {
            Arquivo arquivo = new Arquivo(
                    file.getOriginalFilename(),
                    file.getContentType(),
                    file.getBytes());
            System.out.println("Salvando arquivo: " + arquivo.getName() + " Tipo: " + arquivo.getType());
            this.arquivoRepository.save(arquivo);
        } catch (Exception e) {
            throw new ErroAoSalvar("Erro ao tentar salvar");
        }
    }

    public List<Arquivo> list() {
        return this.arquivoRepository.findAll().orElseThrow(() -> new ErroAoBaixar("Nenhum arquivo encontrado"));
    }

    public Resource download(Long id) {
        Arquivo arquivo = this.arquivoRepository.findById(id)
                .orElseThrow(() -> new ErroAoBaixar("Arquivo não encontrado"));
        return new ByteArrayResource(arquivo.getContent());
    }

}
