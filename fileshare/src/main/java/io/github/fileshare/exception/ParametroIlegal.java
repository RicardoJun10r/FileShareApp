package io.github.fileshare.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(value = HttpStatus.BAD_REQUEST, reason = "Argumentos inválidos")
public class ParametroIlegal extends RuntimeException {

    public ParametroIlegal(String message) {
        super(message);
    }

}
