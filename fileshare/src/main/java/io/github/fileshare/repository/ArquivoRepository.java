package io.github.fileshare.repository;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicLong;

import org.springframework.stereotype.Component;

import io.github.fileshare.exception.ArquivoNaoEncontrado;
import io.github.fileshare.exception.ParametroIlegal;
import io.github.fileshare.model.Arquivo;

@Component
public class ArquivoRepository {

    private Map<Long, Arquivo> arquivos;

    private AtomicLong idGenerator = new AtomicLong(0);

    public ArquivoRepository() {
        this.arquivos = new HashMap<>();
    }

    public void save(Arquivo arquivo) {
        if (arquivo == null) {
            throw new ParametroIlegal("Arquivo ou ID não podem ser nulos");
        }

        if (arquivo.getId() == null) {
            arquivo.setId(idGenerator.incrementAndGet());
        }

        this.arquivos.put(arquivo.getId(), arquivo);
    }

    public Optional<Arquivo> findById(Long id) {
        if (id == null) {
            throw new ParametroIlegal("ID não pode ser nulo");
        }
        Arquivo arquivo = this.arquivos.get(id);
        if (arquivo == null) {
            throw new ArquivoNaoEncontrado("Arquivo não encontrado");
        }
        return Optional.ofNullable(arquivo);
    }

    public Optional<List<Arquivo>> findAll() {
        return Optional.ofNullable(new ArrayList<>(this.arquivos.values()));
    }

    public void delete(Long id) {
        if (id == null) {
            throw new ParametroIlegal("ID não pode ser nulo");
        }
        if (!this.arquivos.containsKey(id)) {
            throw new ArquivoNaoEncontrado("Arquivo não encontrado");
        }
        this.arquivos.remove(id);
    }

}