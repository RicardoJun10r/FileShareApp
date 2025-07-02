package io.github.fileshare.config;

import java.time.LocalTime;
import java.util.List;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import io.github.fileshare.model.Arquivo;
import io.github.fileshare.repository.ArquivoRepository;
import lombok.RequiredArgsConstructor;

@Component
@RequiredArgsConstructor
public class Scheduler {

    private final ArquivoRepository arquivoRepository;

    @Scheduled(cron = "0 */2 * * * *")
    public void task() {
        this.deleteExpiredFiles();
    }

    private void deleteExpiredFiles() {
        List<Arquivo> arquivos = this.arquivoRepository.findAll().get();
        if (arquivos.isEmpty()) {
            return;
        }
        for (Arquivo arquivo : arquivos) {
            if (arquivo != null && arquivo.getExpirationTime().isBefore(LocalTime.now())) {
                this.arquivoRepository.delete(arquivo.getId());
            }
        }
    }
}
