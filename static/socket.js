var currentURL = window.location.pathname;
var dmPattern = /^\/dm\/[a-zA-Z0-9]*/;
socket = io();

$(document).ready(function(){
    socket.on("addUser", function(user) {
        if ($("#"+user.id).length === 0){
            // avoid duplicates
            $("#onlineUsers").append(
                "<tr id=\""+user.id+"\"><td id=\"username\"><a href=\"profile/"+user.id+"\"><button class=\"userButton\">"+user.username+"</button></a></td>" +
                "<td id=\"wins\">"+user.wins+"</td>" +
                "<td id=\"message-button\"><a href=\"dm/"+user.id+"\"><button class=\"userButton\">Message</button></a></td></tr>");
        }
    });

    socket.on("addGame", function(response) {
        if ($("#"+response.gameID).length === 0){
            $("#availableGames").append(
                "<tr id=\""+response.gameID+"\"><td id=\"username\">"+response.username+"'s game</td>" +
                "<td id=\"play-button\"><form action=\"/join/"+response.gameID+"\" id=\"join-form\" method=\"POST\" enctype=\"multipart/form-data\"><button class=\"userButton\">Join Game</button></form></td></tr>");
        }
    });

    socket.on("removeGame", function(response) {
        $("#"+response.gameID).remove();
    });
    
    socket.on('removeUser', (user) => {
        $("#"+user.id).remove();
    });

    socket.on('connect', function() {
        socket.emit('registerID', {id: socket.id});
    });
    
    socket.on('pingUser', function(msg) {
        alert(msg.message)
    });

    socket.on('addDM', function (json_data) {
        // Clean up code once everything is working
        var otherID = window.location.pathname.split("/").pop();
        let sender_id = json_data["sender_id"];
        let receiver_id = json_data["receive_id"];
        let message = json_data["message"];
        let user = json_data["uid"];

        if(user === sender_id) {
            $("#messages").append(
                "<div class=\"my-container\">\n" +
                "<h4 class=\"messageTxt\"> " + message + " </h4>\n" +
                "</div>\n");
        }
        else if(user === receiver_id && otherID === sender_id) {
            $("#messages").append(
                "<div class=\"friend-container\">\n" +
                // "<img src=\"me.jpeg\"" + "alt=\"Picture cannot be found\">\n" +
                "<h4 class=\"messageTxt\"> " + message + " </h4>\n" +
                "</div>\n");
        }

        if (user === receiver_id){
            alert("You have a new message!");
        }

    });
});

function messageSend(recipient, user) {
    let message = document.getElementById("typemsg").value;
    if(message !== "") {
        document.getElementById("typemsg").value = "";
        socket.emit("sendDM", {receiver: recipient, sender: user, mess: message});
    }
}