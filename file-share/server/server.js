import express from 'express';
import { createServer } from 'http';
import { Server } from 'socket.io';

const app = express();
const server = createServer(app);

const io = new Server(server, {
  cors: {
    origin: '*', // Ajuste conforme necessário
    methods: ['GET', 'POST'],
  },
});

let sharedFiles = [];

io.on('connection', (socket) => {
  console.log('Um usuário se conectou');

  // Enviar arquivos compartilhados ao cliente que se conectou
  socket.emit('sharedFiles', sharedFiles);

  // Receber arquivo do cliente e compartilhar com outros
  socket.on('uploadFile', (file) => {
    sharedFiles.push(file);
    io.emit('sharedFiles', sharedFiles);
  });

  socket.on('disconnect', () => {
    console.log('Usuário desconectado');
  });
});

server.listen(3001, () => {
  console.log('Servidor rodando na porta 3001');
});
