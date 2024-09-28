import express from 'express';
import { createServer } from 'http';
import { Server } from 'socket.io';

const app = express();
const server = createServer(app);
const io = new Server(server, {
    cors: {
        origin: 'http://192.168.1.172:5173',  // Substitua pela origem correta do seu cliente
        methods: ['GET', 'POST'],
        allowedHeaders: ['my-custom-header'],
        credentials: true
    }
});

let sharedFiles = []; // Armazenar os arquivos compartilhados

// Rota para a API (opcional)
app.get('/api', (req, res) => {
    res.json({ message: 'Servidor está funcionando!' });
});

// Quando um cliente se conecta via WebSocket
io.on('connection', (socket) => {
    console.log('Um usuário se conectou');

    // Enviar arquivos compartilhados ao cliente que se conectou
    socket.emit('sharedFiles', sharedFiles);

    // Receber arquivo do cliente e compartilhar com outros
    socket.on('uploadFile', (file) => {
        sharedFiles.push(file);
        io.emit('sharedFiles', sharedFiles); // Atualizar todos os clientes
    });

    socket.on('disconnect', () => {
        console.log('Usuário desconectado');
    });
});

// Defina a porta em que o servidor será executado
server.listen(3001, () => {
    console.log('Servidor rodando na porta 3001');
});
