package io.github.fileshare;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@EnableScheduling
@SpringBootApplication
public class FileshareApplication {

	public static void main(String[] args) {
		SpringApplication.run(FileshareApplication.class, args);
	}

}
