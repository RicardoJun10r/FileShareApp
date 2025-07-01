package io.github.fileshare.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(value = HttpStatus.NOT_FOUND, reason = "Arquivo não encontrado")
public class ArquivoNaoEncontrado extends RuntimeException {

    public ArquivoNaoEncontrado(String message) {
        super(message);
    }

}
