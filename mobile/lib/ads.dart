// Copyright (c) 2026 SHAR-K. MPL-2.0.
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';

/// Consent and banner ads (AdMob). Ads are requested only after the Google User
/// Messaging Platform says consent has been gathered where it is required.
class AdService {
  AdService();

  static const _channel = MethodChannel('eyggdranex.mobile/ads');

  /// True once ads may be requested and the SDK is initialized.
  final ValueNotifier<bool> ready = ValueNotifier(false);

  /// True when the user must be able to reopen the consent choices (e.g. in the EEA).
  final ValueNotifier<bool> privacyOptionsRequired = ValueNotifier(false);
  String? bannerId;
  bool _started = false;

  Future<void> start() async {
    if (_started) return;
    _started = true;
    try {
      bannerId = await _channel.invokeMethod<String>('bannerId');
      await _updateConsent();
      await _refresh();
    } catch (_) {
      // Without consent information or the SDK the app simply shows no ads.
      ready.value = false;
    }
  }

  Future<void> _updateConsent() {
    final done = Completer<void>();
    ConsentInformation.instance.requestConsentInfoUpdate(
      ConsentRequestParameters(),
      () async {
        try {
          await ConsentForm.loadAndShowConsentFormIfRequired((_) {});
        } finally {
          if (!done.isCompleted) done.complete();
        }
      },
      (_) {
        if (!done.isCompleted) done.complete();
      },
    );
    return done.future;
  }

  Future<void> _refresh() async {
    privacyOptionsRequired.value =
        await ConsentInformation.instance
            .getPrivacyOptionsRequirementStatus() ==
        PrivacyOptionsRequirementStatus.required;
    if (await ConsentInformation.instance.canRequestAds()) {
      if (!ready.value) await MobileAds.instance.initialize();
      ready.value = true;
    } else {
      ready.value = false;
    }
  }

  /// Reopens the consent choices; ads follow the new answer.
  Future<void> showPrivacyOptions() async {
    try {
      await ConsentForm.showPrivacyOptionsForm((_) {});
      await _refresh();
    } catch (_) {
      // Nothing to show on this device or region.
    }
  }
}

/// Shows no ads; used by tests and builds without the ads plugin.
class NoAds extends AdService {
  @override
  Future<void> start() async {}
}

/// An anchored adaptive banner. Takes no space until an ad has loaded.
class AdBanner extends StatefulWidget {
  const AdBanner({super.key, required this.ads});

  final AdService ads;

  @override
  State<AdBanner> createState() => _AdBannerState();
}

class _AdBannerState extends State<AdBanner> {
  BannerAd? _ad;
  bool _loaded = false;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    widget.ads.ready.addListener(_load);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _load();
  }

  Future<void> _load() async {
    final id = widget.ads.bannerId;
    if (!widget.ads.ready.value || id == null || _ad != null || _loading) {
      return;
    }
    _loading = true;
    final width = MediaQuery.sizeOf(context).width.truncate();
    final size = await AdSize.getLargeAnchoredAdaptiveBannerAdSize(width);
    if (!mounted || size == null) {
      _loading = false;
      return;
    }
    final ad = BannerAd(
      adUnitId: id,
      size: size,
      request: const AdRequest(),
      listener: BannerAdListener(
        onAdLoaded: (_) {
          if (mounted) setState(() => _loaded = true);
        },
        onAdFailedToLoad: (ad, _) {
          ad.dispose();
          if (mounted) {
            setState(() {
              _ad = null;
              _loaded = false;
            });
          }
        },
      ),
    );
    _ad = ad;
    _loading = false;
    await ad.load();
  }

  @override
  void dispose() {
    widget.ads.ready.removeListener(_load);
    _ad?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ad = _ad;
    if (!_loaded || ad == null) return const SizedBox.shrink();
    return Container(
      color: const Color(0xff0b1417),
      // A gap above the navigation bar so the ad is not tapped by accident.
      padding: const EdgeInsets.only(top: 4, bottom: 8),
      alignment: Alignment.center,
      child: SizedBox(
        width: ad.size.width.toDouble(),
        height: ad.size.height.toDouble(),
        child: AdWidget(ad: ad),
      ),
    );
  }
}
