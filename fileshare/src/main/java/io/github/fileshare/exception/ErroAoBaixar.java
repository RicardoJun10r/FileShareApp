package io.github.fileshare.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(value = HttpStatus.NOT_FOUND)
public class ErroAoBaixar extends RuntimeException {

    public ErroAoBaixar(String message) {
        super(message);
    }

}
