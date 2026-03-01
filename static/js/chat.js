const socket = io();

const messages = document.getElementById("messages");
const input = document.getElementById("messageInput");

socket.on("connect", () => {
    console.log("Connected to server");

    socket.emit("join_channel", { channel: CHANNEL_ID });
});

socket.on("server_message", (data) => {
    addMessage(data);
});

socket.on("receive_message", (data) => {
    addMessage(data);
});

function sendMessage() {
    const text = input.value;

    socket.emit("send_message", {
        channel: CHANNEL_ID,
        message: text
    });

    input.value = "";
}

function addMessage(text) {
    const li = document.createElement("li");
    li.textContent = text.username + " - " + text.message;
    messages.appendChild(li);
}
