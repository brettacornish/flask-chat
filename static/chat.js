const socket = io();

const messages = document.getElementById("messages");
const input = document.getElementById("messageInput");

socket.on("connect", () => {
    console.log("Connected to server");
});

socket.on("server_message", (data) => {
    addMessage("[SERVER] " + data.msg);
});

socket.on("receive_message", (data) => {
    addMessage(data.message);
});

function sendMessage() {
    const text = input.value;

    socket.emit("send_message", {
        message: text
    });

    input.value = "";
}

function addMessage(text) {
    const li = document.createElement("li");
    li.textContent = text;
    messages.appendChild(li);
}
