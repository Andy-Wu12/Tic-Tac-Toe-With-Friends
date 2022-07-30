
$(document).ready(function(){
    const gameID = window.location.pathname.split("/").pop();
    opponentID = "";
    
    socket = io();
    const TicTacToe = new TicTacToeGame(socket);
    socket.on('connect', () => {
        // registers user and sends game data if player2
        socket.emit("getGameData", {id: gameID})
    });
    
    socket.on('recieveGameData', (response) => {
        // recieve game data if player2
        console.log("recieved");
        opponentID = response.opponent;
        var waitText = document.getElementById("wait");
        waitText.innerText = "";
    });
    
    socket.on('opponenetJoined', (response) => {
        console.log("opponenetJoined");
        opponentID = response.opponent;
        var waitText = document.getElementById("wait");
        waitText.innerText = "";
        TicTacToe.start();
    });
    
    function TicTacToeGame(socket)
    {
        const game = new Game();
        const player = new Player(game, socket);
        
        socket.on('newTurn', (response) => {
            // add move to square, this opponent is always o
            console.log("my turn");
            var moveLocation = document.getElementById(response.move);
            moveLocation.innerText = 'o';
            player.turn();
        })

        socket.on('lostGame', (response) => {
            // add move to square, this opponent is always o
            console.log("opponent won");
            var moveLocation = document.getElementById(response.move);
            moveLocation.innerText = 'o';
            if (game.checkWinner()){
                setTimeout(() => {
                    console.log("LOST");
                    alert("You lost!");
                    window.location.replace("http://" + window.location.host + "/games");
                }, 1000);
            }
        })

        socket.on('gameTied', (response) => {
            // add move to square, this opponent is always o
            console.log("tied Game");
            var moveLocation = document.getElementById(response.move);
            moveLocation.innerText = 'o';
            if (game.checkTie()){
                setTimeout(() => {
                    console.log("TIE");
                    alert("You tied!");
                    window.location.replace("http://" + window.location.host + "/games");
                }, 1000);
            }
        })
        
        this.start = function()
        {
            player.turn();
        }
    }
    
    function Game()
    {
        this.positions= Array.from(document.querySelectorAll('.col'));  
        
        this.checkTie = () => {
            const positions = this.positions;
            var empty = positions.filter(p => p.innerText !== '');
            return empty.length === 9;
        }

        this.checkWinner = function()
        {
            let winner = false; 
            const winningCombinations = [[0,1,2],[3,4,5],[6,7,8],[0,4,8],[2,4,6],[0,3,6],[1,4,7],[2,5,8]];
            const positions = this.positions;
            winningCombinations.forEach((combo) => {
              const pos0 = positions[combo[0]].innerText;
              const pos1 = positions[combo[1]].innerText;
              const pos2 = positions[combo[2]].innerText;
              const isWinningCombo = pos0!== '' && pos0 === pos1 && pos1 === pos2;
    
                if(isWinningCombo)
                {
                    winner = true;
                    combo.forEach((i)=>{
                        positions[i].className += ' winner';
                    })
                }
    
            });
    
            return winner;
        }
    }
    
    function Player(game, socket)
    {
          this.turn = function(){
              game.positions.forEach(i => {
                  if (i.innerText === ""){
                    i.addEventListener('click', endTurn)
                  }});
          }
    
          function endTurn(event){
              event.target.innerText ='x';
              game.positions.forEach(i => i.removeEventListener('click',endTurn));
              if (game.checkWinner()){
                setTimeout(() => {
                    alert("Winner!");
                    window.location.replace("http://" + window.location.host + "/games");
                }, 1000);
                
                socket.emit("wonGame", {moveLocation: event.target.id, opponent: opponentID, gameID: gameID})
                  // send socket to oppoenet telling them they lost
              }
              else if (game.checkTie()){
                setTimeout(() => {
                    alert("You tied!");
                    window.location.replace("http://" + window.location.host + "/games");
                }, 1000);
                socket.emit("tieGame", {moveLocation: event.target.id, opponent: opponentID, gameID: gameID})
              }
              else{
                socket.emit("endTurn", {moveLocation: event.target.id, opponent: opponentID})
              }

          }
    }
})
