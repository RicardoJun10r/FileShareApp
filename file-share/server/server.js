import express from 'express';
import { createServer } from 'https';
import { Server } from 'socket.io';
import fs from 'fs';

const app = express();
// Use os arquivos gerados pelo mkcert
const privateKey = fs.readFileSync('./192.168.1.170+2-key.pem', 'utf-8');
const certificate = fs.readFileSync('./192.168.1.170+2.pem', 'utf-8');
const credentials = { key: privateKey, cert: certificate };
const server = createServer(credentials, app);

const io = new Server(server, {
  cors: {
    origin: '*',
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
    console.log('recebido arquivo: ', file)
    sharedFiles.push(file);
    io.emit('sharedFiles', sharedFiles);
  });

  socket.on('disconnect', () => {
    console.log('Usuário desconectado');
  });
});

const PORT = 3001;
const HOST = '192.168.1.170'

server.listen(PORT, HOST, () => {
  console.log(`Servidor rodando na porta ${HOST}:${PORT}`);
});