/* Original controlled audit action, Apache-2.0. Never a simulated audit record. */
#include <unistd.h>
int main(void) {
  static const char message[] = "detectbridge controlled audit action\n";
  return write(STDOUT_FILENO, message, sizeof(message) - 1) == sizeof(message) - 1 ? 0 : 1;
}
