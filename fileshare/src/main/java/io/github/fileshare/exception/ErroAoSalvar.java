package io.github.fileshare.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(value = HttpStatus.BAD_REQUEST)
public class ErroAoSalvar extends RuntimeException {

    public ErroAoSalvar(String message) {
        super(message);
    }

}
