# opaline-cipher

<img src=https://github.com/user-attachments/assets/6ccced97-d7fa-4c10-99db-c7a4ae052554>


<br>
<br>
Takes a file and makes it into an image
<br>
<br>
-=-
<br>
<br>
This is a script that both encrypts and decrypts text through the medium of color, written entirely in Python.
<br>
<br>
Opaline is a lightweight, simple script that can encrypt any file into an image, and decrypt it back again. You can also add as many keys as you need to the cipher in order to make it significantly more difficult to decode, and you can encrypt/decrypt images in any width and height. For example, here's the entire Bee Movie script (in .txt format), encrypted with Prism (no ciphers used). Feel free to use my program to decrypt it!
<p> </p>
<img src=https://github.com/user-attachments/assets/f2ca46ff-28ae-4651-8b3c-28ee4ff9d114>
<br>
<h2>How to Install & Use</h2>
The setup process, mostly owing to the simplicity of the program, is easy. The program, because it is an image editor, requires <a href=https://pypi.org/project/pillow/ target="_blank" rel="noopener noreferrer">Pillow</a>. You may have to install it using pip if you do not have it already.
<br> <br>
Once you download the file, open your preferred terminal and go to the folder you have created (or the folder it is located in) with cd. Then, run it in Python.
<br> <br>
To use the program, you must first select a target file directory to encrypt or decrypt. You can do this by choosing option 3 in the main menu. After you have done so, the program will send you back to the main menu with your file selected. To turn your file into an image, press 1, and the program will walk you through the process. Decrypting an already encrypted image follows a similar process, but keep in mind that you will have to provide your own file extension as well. This means that you will have to include the type of file you want the program to decrypt the image into, such as "img.jpg", "text.txt", or "archive.zip".
<h2>Update Plan</h2>
<ul>
  <li>✅ - Support for encryption/decryption in WAV</li>
  <li>⬜ - Support for encryption/decryption in MP4</li>
</ul>
