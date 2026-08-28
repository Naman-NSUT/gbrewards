import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  FlatList,
  Image,
  LayoutChangeEvent,
  NativeScrollEvent,
  NativeSyntheticEvent,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

import { resolveBannerUrl, type Banner } from '../api/banners';
import { useBanners } from '../hooks/useBanners';
import { colors, spacing } from '../theme';

const HEIGHT = 170;
const AUTO_ADVANCE_MS = 4000;

function Slide({ banner, width }: { banner: Banner; width: number }) {
  return (
    <View style={[styles.slide, { width }]}>
      <View style={styles.imageWrap}>
        <Image
          source={{ uri: resolveBannerUrl(banner.image_url) }}
          style={styles.image}
          resizeMode="cover"
        />
        {banner.caption ? (
          <LinearGradient
            colors={['transparent', 'rgba(14,51,70,0.72)']}
            style={styles.scrim}
          >
            <Text style={styles.caption} numberOfLines={2}>
              {banner.caption}
            </Text>
          </LinearGradient>
        ) : null}
      </View>
    </View>
  );
}

export function BannerCarousel() {
  const { data, isLoading } = useBanners();
  const banners = data ?? [];
  const count = banners.length;

  const [width, setWidth] = useState(0);
  const [index, setIndex] = useState(0);
  const listRef = useRef<FlatList<Banner>>(null);

  const onLayout = useCallback((e: LayoutChangeEvent) => {
    setWidth(e.nativeEvent.layout.width);
  }, []);

  // Auto-advance (wrapping) when there is more than one banner and we know the
  // slide width. The effect re-runs on every `index` change, so its closure
  // always sees the current index; manual scrolls (which set index) reset the
  // timer too.
  useEffect(() => {
    if (count <= 1 || width === 0) return;
    const id = setInterval(() => {
      const next = (index + 1) % count;
      listRef.current?.scrollToOffset({ offset: next * width, animated: true });
      setIndex(next);
    }, AUTO_ADVANCE_MS);
    return () => clearInterval(id);
  }, [count, width, index]);

  const onMomentumScrollEnd = useCallback(
    (e: NativeSyntheticEvent<NativeScrollEvent>) => {
      if (width === 0) return;
      // setIndex bails out when the value is unchanged, so no manual guard needed.
      setIndex(Math.round(e.nativeEvent.contentOffset.x / width));
    },
    [width],
  );

  if (isLoading || count === 0) return null;

  return (
    <View style={styles.root} onLayout={onLayout}>
      {width > 0 ? (
        <FlatList
          ref={listRef}
          data={banners}
          keyExtractor={(b) => b.id}
          renderItem={({ item }) => <Slide banner={item} width={width} />}
          horizontal
          pagingEnabled
          showsHorizontalScrollIndicator={false}
          onMomentumScrollEnd={onMomentumScrollEnd}
          getItemLayout={(_, i) => ({ length: width, offset: width * i, index: i })}
        />
      ) : (
        <View style={{ height: HEIGHT }} />
      )}

      {count > 1 ? (
        <View style={styles.dots}>
          {banners.map((b, i) => (
            <View
              key={b.id}
              style={[styles.dot, i === index ? styles.dotActive : styles.dotInactive]}
            />
          ))}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    marginTop: spacing.md,
  },
  slide: {
    paddingHorizontal: spacing.md,
  },
  imageWrap: {
    height: HEIGHT,
    borderRadius: 16,
    overflow: 'hidden',
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  image: {
    width: '100%',
    height: '100%',
  },
  scrim: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.lg,
    paddingBottom: spacing.md,
    justifyContent: 'flex-end',
  },
  caption: {
    color: colors.onPrimary,
    fontSize: 14,
    fontWeight: '700',
  },
  dots: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: spacing.sm,
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 7,
    marginHorizontal: 3,
  },
  dotActive: {
    backgroundColor: colors.primary,
  },
  dotInactive: {
    backgroundColor: colors.faint,
  },
});
