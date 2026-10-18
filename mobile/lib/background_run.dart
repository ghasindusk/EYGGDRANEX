import 'package:flutter/services.dart';

/// Controls the Android foreground service that keeps simulation ticks running.
class BackgroundRunController {
  const BackgroundRunController();

  static const _channel = MethodChannel('eyggdranex.mobile/background_run');

  Future<bool> start() async =>
      await _channel.invokeMethod<bool>('start') ?? false;

  Future<void> stop() async {
    await _channel.invokeMethod<bool>('stop');
  }
}
